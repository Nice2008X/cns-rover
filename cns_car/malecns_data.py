"""Independent MaleCNS v1.0 import and car circuit construction.

No imports, matrices, checkpoints or code from fly-brain-codex/brain.py.
The vendored natverse package specifies the dataset and offers the R export
route. The public flat snapshot is the token-free equivalent data source.
"""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

DATASET = 'male-cns:v1.0'
BASE = 'https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/'
FILES = {
    'annotations.feather': ('body-annotations-male-cns-v1.0-minconf-0.5.feather', 14_483_314),
    'weights.feather': ('connectome-weights-male-cns-v1.0-minconf-0.5.feather', 1_051_241_946),
}
SNAPSHOT_SHA256 = {
    'annotations.feather': '2177e246113e4cfbf1e7772ec37c6da1955ff22e8063d0b1f833101f99a9a3b2',
    'weights.feather': 'e35da783d1c686b2b58b3b87cd6a403ae43bfcfba8bff28e08ef752c1a56afc1',
}
# Small visual projection population, chosen by annotation, not copied circuits.
VISUAL_TYPES = ('LC4', 'LC6', 'LC11', 'LPLC1', 'LPLC2')
BINS = 7


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def fetch_snapshot(directory):
    """Download the pinned public snapshot; never promote incomplete downloads.

    Pins were measured on initial acquisition, not upstream signed checksums.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, (remote, pinned_size) in FILES.items():
        path = directory / name
        if path.exists():
            if path.stat().st_size != pinned_size or digest(path) != SNAPSHOT_SHA256[name]:
                raise ValueError(f'Wrong size for cached snapshot: {path}')
            continue
        partial = path.with_suffix('.part')
        try:
            with urlopen(BASE + remote, timeout=60) as response, partial.open('wb') as out:
                expected = int(response.headers['Content-Length'])
                if expected != pinned_size:
                    raise ValueError('Unexpectedly large MaleCNS download')
                total = 0
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > expected:
                        raise ValueError('Download exceeded declared size')
                    out.write(block)
            if total != expected or digest(partial) != SNAPSHOT_SHA256[name]:
                raise ValueError('Incomplete MaleCNS download')
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)
    return directory


def build_circuit(source='data/malecns-raw', output='data/malecns-car',
                  vendor='vendor/malecns', limit=384):
    """Extract actual visual outgoing and downstream recurrent synapse counts.

    Source is either the public Feather pair or export_malecns.R's CSV pair.
    All retained edges have >=5 synapses. Unsigned weights are deliberately
    used as excitatory rate couplings; no neurotransmitter claims are made.
    """
    import numpy as np
    from scipy import sparse
    source, output, vendor = Path(source), Path(output), Path(vendor)
    if not 32 <= limit <= 2048:
        raise ValueError('Circuit limit must be between 32 and 2048')
    vendor_files = ['DESCRIPTION', 'R/neuprint.R', 'R/urls.R', 'R/zzz.R']
    if not all((vendor / p).is_file() for p in vendor_files):
        raise ValueError('The vendored natverse/malecns source is required')
    if DATASET not in (vendor / 'R/zzz.R').read_text():
        raise ValueError('Vendored dataset does not match the pinned snapshot')
    if (source / 'export.json').exists():
        import csv
        provenance = json.loads((source / 'export.json').read_text())
        if provenance.get('dataset') != DATASET or provenance.get('source') != 'natverse/malecns':
            raise ValueError('Expected a MaleCNS v1.0 R export')
        with (source / 'neurons.csv').open() as f:
            neurons = list(csv.DictReader(f))
        def batches():
            with (source / 'edges.csv').open() as f:
                chunk = []
                for row in csv.DictReader(f):
                    chunk.append([int(row[k]) for k in ('body_pre', 'body_post', 'weight')])
                    if len(chunk) == 65536:
                        yield np.asarray(chunk, dtype=np.int64).T
                        chunk = []
                if chunk:
                    yield np.asarray(chunk, dtype=np.int64).T
        source_files = ['export.json', 'neurons.csv', 'edges.csv']
    else:
        for name, (_, size) in FILES.items():
            path = source / name
            if path.stat().st_size != size or digest(path) != SNAPSHOT_SHA256[name]:
                raise ValueError(f'Official MaleCNS snapshot checksum mismatch: {name}')
        import pyarrow.feather as feather
        import pyarrow.ipc as ipc
        neurons = feather.read_table(source / 'annotations.feather').to_pylist()
        def batches():
            with ipc.open_file(source / 'weights.feather') as reader:
                for i in range(reader.num_record_batches):
                    batch = reader.get_batch(i)
                    yield tuple(batch.column(batch.schema.get_field_index(k)).to_numpy()
                                for k in ('body_pre', 'body_post', 'weight'))
        source_files = list(FILES)
        provenance = {'source': 'Janelia public flat snapshot', 'dataset': DATASET,
                      'urls': {k: BASE + v[0] for k, v in FILES.items()}}
    metadata = {int(r['bodyId']): r for r in neurons if r.get('bodyId')}
    visual = sorted(i for i, r in metadata.items()
                    if r.get('type') in VISUAL_TYPES and r.get('somaSide') in ('L', 'R'))
    if not visual:
        raise ValueError('No annotated visual input neurons in the source')
    visual_ids = np.asarray(visual, dtype=np.int64)
    # Partner ranking is restricted to annotated central/descending neurons.
    eligible = np.array(sorted(i for i, r in metadata.items()
                               if r.get('superclass') in ('cb_intrinsic', 'descending_neuron')))
    totals = {}
    print('Ranking MaleCNS visual partners...', flush=True)
    for pre, post, weight in batches():
        keep = (weight >= 5) & np.isin(pre, visual_ids) & np.isin(post, eligible)
        for body, n in zip(post[keep], weight[keep]):
            totals[int(body)] = totals.get(int(body), 0) + int(n)
    downstream = sorted(sorted(totals, key=lambda i: (-totals[i], i))[:limit])
    if len(downstream) < 32:
        raise ValueError('Insufficient connected visual partners')
    ids = np.asarray(visual + downstream, dtype=np.int64)
    index = {int(body): i for i, body in enumerate(ids)}
    pre_index, post_index, counts = [], [], []
    print('Extracting the independent circuit...', flush=True)
    for pre, post, weight in batches():
        keep = (weight >= 5) & np.isin(pre, ids) & np.isin(post, downstream)
        pre_index.extend(index[int(i)] for i in pre[keep])
        post_index.extend(index[int(i)] - len(visual) for i in post[keep])
        counts.extend(int(w) for w in weight[keep])
    graph = sparse.csr_matrix((np.asarray(counts, dtype=float), (post_index, pre_index)),
                              shape=(len(downstream), len(ids)))
    scale = sparse.diags(1 / np.maximum(np.asarray(graph.sum(axis=1)).ravel(), 1))
    graph = scale @ graph
    # Engineered visual-field mapping, explicitly not biological retinotopy.
    # LC11 receives target salience, other selected types receive proximity.
    channels = np.empty(len(visual), dtype=np.int64)
    for target in (False, True):
        for side in ('L', 'R'):
            group = [j for j, body in enumerate(visual)
                     if (metadata[body]['type'] == 'LC11') == target
                     and metadata[body]['somaSide'] == side]
            if not group:
                raise ValueError('Both visual hemispheres and channels are required')
            bins = [0, 1, 2, 3] if side == 'L' else [3, 4, 5, 6]
            for k, j in enumerate(group):
                channels[j] = bins[k % len(bins)] + (0 if target else BINS)
    injection = sparse.csr_matrix((np.ones(len(visual)), (np.arange(len(visual)), channels)),
                                  shape=(len(visual), 2 * BINS))
    output.mkdir(parents=True, exist_ok=True)
    sparse.save_npz(output / 'feed.npz', (graph[:, :len(visual)] @ injection).tocsr())
    sparse.save_npz(output / 'recurrent.npz', graph[:, len(visual):].tocsr())
    np.savez_compressed(output / 'anatomy.npz', body_ids=ids, pre=np.asarray(pre_index),
                        post=np.asarray(post_index) + len(visual), synapses=np.asarray(counts),
                        input_channels=channels)
    (output / 'neurons.json').write_text(json.dumps([
        {k: metadata[int(i)].get(k) for k in ('bodyId', 'type', 'somaSide', 'superclass')}
        for i in ids], indent=2))
    info = {'schema': 'malecns-car-circuit-v1', 'dataset': DATASET, 'provenance': provenance,
            'source_sha256': {name: digest(source / name) for name in source_files},
            'vendor_sha256': {name: digest(vendor / name) for name in vendor_files},
            'visual_types': VISUAL_TYPES, 'visual_neurons': len(visual),
            'downstream_neurons': len(downstream), 'anatomical_edges': len(counts),
            'selection': f'top {limit} central/descending partners of selected visual types; >=5 synapses',
            'encoding': '7 target + 7 proximity sectors; soma side and body-ID order mapping, not retinotopy',
            'dynamics': '4 tanh rate iterations from zero; unsigned normalized synapse counts',
            'biologically_validated': False, 'license': 'CC-BY-4.0',
            'files': {name: digest(output / name) for name in
                      ('feed.npz', 'recurrent.npz', 'anatomy.npz', 'neurons.json')}}
    (output / 'ATTRIBUTION.md').write_text(
        '# MaleCNS car circuit attribution\n\n'
        'Original MaleCNS v1.0 data: FlyEM / HHMI Janelia, University of Cambridge,\n'
        'MRC Laboratory of Molecular Biology, Google Research, and collaborators.\n'
        'Source: https://male-cns.janelia.org/download/\n'
        'License: CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/\n\n'
        'CNS Car transformations: visual/central subgraph extraction, normalized\n'
        'unsigned weights, engineered visual sectors and rate dynamics, and a new\n'
        'car readout. No Fly Brain Codex assets. Not biologically validated.\n'
        'Source URLs, original body IDs and hashes are retained with this model.\n')
    (output / 'manifest.json').write_text(json.dumps(info, indent=2))
    return info


def train_readout(directory='data/malecns-car', seed=2718, samples=6000):
    """Fit an engineered sensory-to-car readout, independent of the old policy.

    The targets are bearing, avoidance bias and proximity, not fly motor labels.
    Held-out sensory errors are distinct from closed-loop navigation results.
    """
    import numpy as np
    from .malecns_controller import RateCircuit
    directory = Path(directory)
    circuit = RateCircuit(directory, readout=False)
    rng = np.random.default_rng(seed)
    inputs = rng.uniform(0, 1, (samples + 1000, 2 * BINS))
    # Target sectors form a normalized angular distribution or no detection.
    bearing = rng.uniform(0, BINS - 1, len(inputs))
    target = np.exp(-((np.arange(BINS)[None, :] - bearing[:, None]) / .65) ** 2)
    target /= target.sum(axis=1, keepdims=True)
    target[rng.random(len(inputs)) < .2] = 0
    inputs[:, :BINS] = target
    inputs[rng.random(len(inputs)) < .2, BINS:] = 0
    angles = np.linspace(-1, 1, BINS)
    labels = np.column_stack((target @ angles,
                             -(inputs[:, BINS:] @ angles) / 4,
                             inputs[:, BINS:].mean(axis=1)))
    features = np.asarray([circuit.features(x) for x in inputs])
    mean = features[:samples].mean(axis=0)
    scale = np.maximum(features[:samples].std(axis=0), .001)
    x = np.column_stack(((features - mean) / scale, np.ones(len(features))))
    penalty = np.eye(x.shape[1]) * .05
    penalty[-1, -1] = 0
    weights = np.linalg.solve(x[:samples].T @ x[:samples] + penalty,
                              x[:samples].T @ labels[:samples])
    config = {'schema': 'malecns-car-readout-v1', 'circuit_sha256': digest(directory / 'manifest.json'),
              'seed': seed, 'training_samples': samples, 'validation_samples': 1000,
              'validation_rmse': np.sqrt(np.mean((x[samples:] @ weights - labels[samples:]) ** 2, axis=0)).tolist(),
              'outputs': ['target_bearing', 'avoidance_bias', 'proximity'],
              'teacher': 'engineered sector bearing and proximity equations',
              'biologically_validated': False}
    np.savez_compressed(directory / 'readout.npz', weights=weights, mean=mean, scale=scale,
                        config=json.dumps(config))
    (directory / 'training.json').write_text(json.dumps(config, indent=2))
    return config
