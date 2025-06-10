# Contributing

Thank you for considering contributing to the Mishearing Corpus project!
This document outlines the steps to contribute effectively.

## General Guidelines

1. **Fork -> Branch -> PR**: Always work on a forked repository and create a new branch for your changes.
2. Append CSV files under `/data/mishearing/<description>/`. Don't rearrange column order.
3. Run `frictionless validate --schema schema/*.json data/*.csv` locally until it passes (See below for more detailed command).
   If you activated the precommit, it will run the test automatically.
4. Push your changes; ensure the CI passes.
5. Follow the PR template, which asks for:
   - New `MishearID` range (Maybe tag files, too).
   - Data source (paper / annotation task / synthetic / website).
   - Statement that you own the rights or the excerpt is within quotation limits.

## Adding Tags

To add tags:

1. Open the `data/tag/<description>/` directory.
2. Append new rows with the following columns:
   - `MishearID`: A unique identifier for the tag found in `mishearing/<description>/`.
   - `TagID`: The name of the tag.
3. Commit and push the changes, ensuring the precommit and CI passes.

## Adding Mishearing Data

To add new mishearing data:

1. Open the appropriate shard in `data/mishearing/<description>/`.
2. Append new rows with the following columns:
   - `MishearID`: A unique identifier for the mishearing event.
   - Other columns as defined in `schema/mishearing.schema.json`.
3. Ensure the new rows align with the schema.
4. Run `frictionless validate --schema schema/mishearing.schema.json data/mishearing/<description>/<description>.csv` locally to validate the changes.
5. Commit and push the changes, ensuring the CI passes.

## Running Tests

1. Install dependencies using `pip install -r requirements.txt`.
2. Run tests using `pytest`.
3. Ensure all tests pass before submitting a PR.

## Building Datapackage

1. Run `python scripts/build_datapackage.py` to regenerate `datapackage.json`.
2. Commit the updated `datapackage.json`.

## Pull Request Template

When submitting a pull request, please follow the template provided in `.github/pull_request_template.md`. This ensures:

1. A clear description of the changes and their motivation.
2. Validation of data using `frictionless validate`.
3. Inclusion of tests for new features or fixes.
4. Proper documentation updates.
5. Web archive using https://megalodon.jp/

Refer to the checklist in the template to ensure all steps are completed before submission.

## Reporting Issues

If you encounter any issues, please open a GitHub issue with detailed information about the problem.

Thank you for contributing!