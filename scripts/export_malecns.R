#!/usr/bin/env Rscript
# Run from the project root with the dependencies of vendor/malecns installed.
# devtools::load_all loads this checkout, not a separately installed malecns.
args <- commandArgs(trailingOnly=TRUE)
out <- if (length(args)) args[[1]] else 'data/malecns-export'
if (!requireNamespace('devtools', quietly=TRUE) || !requireNamespace('jsonlite', quietly=TRUE))
  stop('Install devtools, jsonlite and the dependencies in vendor/malecns/DESCRIPTION')
devtools::load_all('vendor/malecns', quiet=TRUE)
malecns::choose_mcns_dataset('male-cns:v1.0')
conn <- malecns::mcns_neuprint()
types <- c('LC4', 'LC6', 'LC11', 'LPLC1', 'LPLC2')
visual <- malecns::mcns_neuprint_meta(paste0('/^(', paste(types, collapse='|'), ')$'), conn=conn)
visual <- visual[visual$somaSide %in% c('L', 'R'), ]
outgoing <- malecns::mcns_connection_table(visual$bodyid, partners='outputs',
  threshold=5L, summary=FALSE, moredetails=FALSE, conn=conn)
partners <- malecns::mcns_neuprint_meta(unique(outgoing$partner), conn=conn)
eligible <- partners$bodyid[partners$superclass %in% c('cb_intrinsic', 'descending_neuron')]
ranks <- aggregate(weight ~ partner, outgoing[outgoing$partner %in% eligible, ], sum)
ranks <- ranks[order(-ranks$weight, ranks$partner), ]
selected <- head(ranks$partner, 384)
recurrent <- malecns::mcns_connection_table(selected, partners='outputs',
  threshold=5L, summary=FALSE, moredetails=FALSE, conn=conn)
# Include every visual partner for the identical Python ranking step.
edges <- rbind(outgoing[, c('bodyid','partner','weight')],
               recurrent[recurrent$partner %in% selected, c('bodyid','partner','weight')])
names(edges) <- c('body_pre','body_post','weight')
neurons <- rbind(visual[, c('bodyid','type','somaSide','superclass')],
                 partners[, c('bodyid','type','somaSide','superclass')])
neurons <- neurons[!duplicated(neurons$bodyid), ]
names(neurons)[1] <- 'bodyId'
dir.create(out, recursive=TRUE, showWarnings=FALSE)
write.csv(neurons, file.path(out, 'neurons.csv'), row.names=FALSE, na='')
write.csv(edges, file.path(out, 'edges.csv'), row.names=FALSE)
jsonlite::write_json(list(source='natverse/malecns', dataset='male-cns:v1.0',
  package_version=as.character(utils::packageVersion('malecns')),
  export_time=format(Sys.time(), tz='UTC', usetz=TRUE)), file.path(out, 'export.json'), auto_unbox=TRUE, pretty=TRUE)
