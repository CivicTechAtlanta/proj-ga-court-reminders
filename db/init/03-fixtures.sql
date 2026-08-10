-- Synthetic case data exercising every filter in the reminder query
-- (db/queries/next_week_hearings.sql). Event dates are anchored to
-- CURRENT_DATE at first container start, so the 7-days-out window matches
-- on day one; `make db-reset` re-anchors them.
--
-- Expected on first run: exactly 7 rows (8 without DISTINCT).
-- All phone numbers use the reserved 555 range so no real number can be texted.

SET search_path TO dbo, public;

INSERT INTO tblParty (PartyID, FirstName, LastName) VALUES
    (1,  'James',  'Moreno'),
    (2,  'Tom',    'Becker'),
    (3,  'Aisha',  'Clark'),
    (4,  'Robert', 'Hale'),
    (5,  'Dana',   'Whitfield'),
    (6,  'Luis',   'Ortega'),
    (7,  'Priya',  'Raman'),
    (8,  'Nina',   'Sato'),
    (9,  'Omar',   'Diallo'),
    (10, 'Grace',  'Lin'),
    (11, 'Victor', 'Nunez');

-- Scenario per case (IN/OUT = whether the reminder query returns it):
--   1 CR-2026-000101 Moreno    IN  1 row - hearing +7d; +30d jury trial excluded;
--                                  co-defendant Becker excluded (not FirstDefendantID)
--   2 CR-2026-000102 Clark     IN  covers PhoneType 'MOBILE'
--   3 CR-2026-000103 Hale      OUT only a HOME phone
--   4 CR-2026-000104 Whitfield IN  event exactly at CURRENT_DATE+7 00:00 (inclusive lower bound)
--   5 CR-2026-000105 Ortega    OUT event exactly at CURRENT_DATE+8 00:00 (exclusive upper bound)
--   6 CR-2026-000106 Raman     OUT event +3d, outside window
--   7 CR-2026-000107 Sato      IN  1 row - duplicate identical CELL rows collapsed by DISTINCT
--   8 CR-2026-000108 Diallo    IN  2 rows - distinct CELL and MOBILE numbers both returned
--   9 CR-2026-000109 Lin       IN  daily status hearings +1..+14d keep the query non-empty
--                                  for a week after first start without a db-reset
--  10 CR-2026-000110 Nunez     OUT no phone row; INNER JOIN drops the case
INSERT INTO tblCase (CaseID, CaseNumber, FirstDefendantID, FiledDate) VALUES
    (1,  'CR-2026-000101', 1,  CURRENT_DATE - 60),
    (2,  'CR-2026-000102', 3,  CURRENT_DATE - 45),
    (3,  'CR-2026-000103', 4,  CURRENT_DATE - 90),
    (4,  'CR-2026-000104', 5,  CURRENT_DATE - 30),
    (5,  'CR-2026-000105', 6,  CURRENT_DATE - 30),
    (6,  'CR-2026-000106', 7,  CURRENT_DATE - 20),
    (7,  'CR-2026-000107', 8,  CURRENT_DATE - 75),
    (8,  'CR-2026-000108', 9,  CURRENT_DATE - 15),
    (9,  'CR-2026-000109', 10, CURRENT_DATE - 120),
    (10, 'CR-2026-000110', 11, CURRENT_DATE - 10);

INSERT INTO tblCaseParty (CaseID, PartyID, ConnectionType) VALUES
    (1, 1,  'DEFENDANT'),
    (1, 2,  'DEFENDANT'),  -- co-defendant, not FirstDefendantID: excluded by the join
    (2, 3,  'DEFENDANT'),
    (3, 4,  'DEFENDANT'),
    (4, 5,  'DEFENDANT'),
    (5, 6,  'DEFENDANT'),
    (6, 7,  'DEFENDANT'),
    (7, 8,  'DEFENDANT'),
    (8, 9,  'DEFENDANT'),
    (9, 10, 'DEFENDANT'),
    (10, 11, 'DEFENDANT');

INSERT INTO tblPartyPhone (PartyID, PhoneType, PhoneNumber) VALUES
    (1,  'CELL',   '+14045550101'),
    (2,  'CELL',   '+14045550102'),
    (3,  'MOBILE', '+14045550103'),
    (4,  'HOME',   '+14045550104'),  -- wrong phone type: excluded
    (5,  'CELL',   '+14045550105'),
    (6,  'CELL',   '+14045550106'),
    (7,  'CELL',   '+14045550107'),
    (8,  'CELL',   '+14045550108'),
    (8,  'CELL',   '+14045550108'),  -- data-entry duplicate: collapsed by DISTINCT
    (9,  'CELL',   '+14045550109'),
    (9,  'MOBILE', '+14045550110'),
    (10, 'CELL',   '+14045550111');
    -- party 11 (Nunez) deliberately has no phone row

INSERT INTO tblEvent (EventID, CourtRoomCode, JudgeName) VALUES
    (1, '1A',  'Judge Alvarez'),
    (2, '2B',  'Judge Brooks'),
    (3, '3C',  'Judge Chen'),
    (4, 'JC1', 'Judge Dawson'),
    (5, '2B',  'Judge Ellis');

-- CaseEventTypeID: 1=ARRAIGN 2=STATUS 3=PRELIM 4=BENCH 5=JURY (02-reference-data.sql)
INSERT INTO tblCaseEvent (CaseID, EventID, CaseEventTypeID, CaseStartDateTime) VALUES
    (1,  1, 1, (CURRENT_DATE + 7)  + time '09:00'),
    (1,  5, 5, (CURRENT_DATE + 30) + time '09:00'),  -- outside window: excluded
    (2,  2, 3, (CURRENT_DATE + 7)  + time '13:30'),
    (3,  1, 2, (CURRENT_DATE + 7)  + time '10:00'),
    (4,  3, 1, (CURRENT_DATE + 7)  + time '00:00'),  -- inclusive lower bound
    (5,  3, 1, (CURRENT_DATE + 8)  + time '00:00'),  -- exclusive upper bound: excluded
    (6,  2, 2, (CURRENT_DATE + 3)  + time '09:30'),  -- outside window: excluded
    (7,  1, 3, (CURRENT_DATE + 7)  + time '10:15'),
    (8,  2, 4, (CURRENT_DATE + 7)  + time '11:00'),
    (10, 1, 1, (CURRENT_DATE + 7)  + time '14:00');

-- Lin's daily status hearings, +1..+14 days out
INSERT INTO tblCaseEvent (CaseID, EventID, CaseEventTypeID, CaseStartDateTime)
SELECT 9, 4, 2, d + interval '8 hours 30 minutes'
FROM generate_series(CURRENT_DATE + 1, CURRENT_DATE + 14, interval '1 day') AS d;

-- Re-sync identity sequences after the explicit-ID inserts above
SELECT setval(pg_get_serial_sequence('dbo.tblparty', 'partyid'),
              (SELECT max(PartyID) FROM tblParty));
SELECT setval(pg_get_serial_sequence('dbo.tblcase', 'caseid'),
              (SELECT max(CaseID) FROM tblCase));
SELECT setval(pg_get_serial_sequence('dbo.tblevent', 'eventid'),
              (SELECT max(EventID) FROM tblEvent));
SELECT setval(pg_get_serial_sequence('dbo.tbleventtype', 'eventtypeid'),
              (SELECT max(EventTypeID) FROM tblEventType));
