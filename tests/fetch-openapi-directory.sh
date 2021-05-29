#!/bin/sh

REPOSRC=https://github.com/APIs-guru/openapi-directory.git
LOCALREPO=tests/openapi-directory

# We do it this way so that we can abstract if from just git later on
LOCALREPO_VC_DIR=$LOCALREPO/.git

if [ ! -d $LOCALREPO_VC_DIR ]
then
    git clone $REPOSRC $LOCALREPO --depth 1
else
    cd $LOCALREPO
    git pull $REPOSRC
fi
