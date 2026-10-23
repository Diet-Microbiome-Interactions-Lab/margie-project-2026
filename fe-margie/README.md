<div align="center">

# MARGIE | Website

**Mostly Automated Rapid Genome Inference Environment**
<br>
MARGIE's interface as a website: sign in with your HPC account, start annotation runs on the cluster, watch them, and read the results.

</div>

## What this folder is

MARGIE's interface (SvelteKit), in `margie-fe/`. It works with an HPC cluster, through
MARGIE's API in [`../be-margie`](../be-margie), which also holds the pipeline the cluster runs.

## Where everything on the cluster is set

Every path lives in the user's MARGIE settings on the cluster, edited on the site's Settings
page: the containers and databases folders, the build recipes, the MARGIE database, the
operon reference, the fingerprint databases and the genome pool, the working folder that
holds a user's copies, and the group's shared folder (optional) that first runs copy from.

## Run it

See [Run the website](../README.md#run-the-website) in the repository's README.
