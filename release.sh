#!/bin/bash -xe
git push --force https://${GH_TOKEN}@github.com/up9inc/mockintosh.git HEAD:gh-pages
sed -ri s/GIT_TAG/$TRAVIS_TAG/ docs/index.md
