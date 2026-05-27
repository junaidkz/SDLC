# ---
# req_id: REQ-AUTH-014
# jira: PLAT-1234
# status: approved
# area: Authentication
# created: 2026-05-22
# owner: platform-team
# ---

Feature: Refresh-token rotation
  As an authenticated user
  I want my refresh token rotated on every use
  So that a stolen token cannot be reused

  Background:
    Given the user is authenticated
    And the user holds a refresh token "T1"

  @REQ-AUTH-014 @AC-1
  Scenario: Successful rotation issues a new token and invalidates the old
    When the client POSTs T1 to /auth/refresh
    Then the response contains a new refresh token "T2"
    And subsequent use of T1 returns 401

  @REQ-AUTH-014 @AC-2
  Scenario: Reuse of an invalidated token raises an audit event
    Given T1 has been rotated to T2
    When the client POSTs T1 to /auth/refresh
    Then the response is 401
    And an audit event "refresh_token_reuse" with severity "WARN" is emitted
    And the audit event carries the user id and source IP

  @REQ-AUTH-014 @AC-3
  Scenario: Rotation latency meets SLA under load
    When 50 RPS of /auth/refresh runs for 60 seconds
    Then p99 latency is below 5 seconds
    And no errors are returned
