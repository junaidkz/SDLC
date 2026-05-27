# ---
# req_id: REQ-LINEAGE-007
# jira: PLAT-1289
# status: approved
# area: Knowledge Fabric
# created: 2026-05-22
# owner: platform-team
# ---

Feature: CSV field-mapping ingestion
  As a data platform operator
  I want field-mapping CSV files ingested idempotently
  So that lineage graphs stay correct and operationally observable

  Background:
    Given a valid CSV mapping file "mappings.csv"
    And the lineage graph store is reachable

  @REQ-LINEAGE-007 @AC-1
  Scenario: Re-running the same CSV is idempotent
    When the ingestion job runs for "mappings.csv"
    And the ingestion job runs again for "mappings.csv"
    Then the second run creates zero new nodes
    And the second run creates zero new edges

  @REQ-LINEAGE-007 @AC-2
  Scenario: Malformed rows are skipped and processing continues
    Given "mappings.csv" contains malformed rows
    When the ingestion job runs for "mappings.csv"
    Then malformed rows are skipped
    And valid rows are still ingested
    And a structured log entry is emitted for each skipped row

  @REQ-LINEAGE-007 @AC-3
  Scenario: Ingestion emits a summary count
    When the ingestion job runs for "mappings.csv"
    Then the output includes summary counts
    And the summary includes "accepted", "skipped", and "errors"
