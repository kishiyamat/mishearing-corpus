# Contributing

Thank you for considering contributing to the Mishearing Corpus project!
This document outlines the steps to contribute effectively.

## General Guidelines

1. **Fork -> Branch -> PR**: Always work on a forked repository and create a new branch for your changes.
2. Append .csv files under /data/mishearing. Don't rearrange column order.
3. Run `frictionless validate --schema schema/*.json data/*.csv` locally until it passes.
   If you activated the precommit, it will run the test automatically.
4. Push your changes; ensure the CI passes.
5. Follow the PR template, which asks for:
   - New `MishearID` range (Maybe tag files, too).
   - Data source (paper / annotation task / synthetic / website).
   - Statement that you own the rights or the excerpt is within quotation limits.

## Adding Tags

To add tags:

1. Open the `data/tag/` directory.
2. Append new rows with the following columns:
   - `MishearID`: A unique identifier for the tag found in `mishearing/`.
   - `TagID`: The name of the tag.
3. Commit and push the changes, ensuring the precommit and CI passes.

## Adding Mishearing Data

To add new mishearing data:

1. Open the appropriate shard in `data/mishearing/`.
2. Append new rows with the following columns:
   - `MishearID`: A unique identifier for the mishearing event.
   - Other columns as defined in `schema/mishearing.schema.json`.
3. Ensure the new rows align with the schema.
4. Run `frictionless validate --schema schema/mishearing.schema.json data/mishearing/*.csv` locally to validate the changes.
5. Commit and push the changes, ensuring the CI passes.

## Running Tests

1. Install dependencies using `pip install -r requirements.txt`.
2. Run tests using `pytest`.
3. Ensure all tests pass before submitting a PR.

## Building Datapackage

1. Run `python scripts/build_datapackage.py` to regenerate `datapackage.json`.
2. Commit the updated `datapackage.json`.

## Reporting Issues

If you encounter any issues, please open a GitHub issue with detailed information about the problem.

Thank you for contributing!