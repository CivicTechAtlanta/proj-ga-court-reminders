-- Synthetic case data exercising every filter in the reminder query
-- (db/queries/next_week_hearings.sql). Event dates are anchored to
-- CURRENT_DATE at first container start, so the 7-days-out window matches
-- on day one; `make db-reset` re-anchors them.
--
-- Expected on first run: exactly 11 rows (12 without DISTINCT).
--
-- Data quality deliberately mirrors the benchmark database — clean rows are
-- the exception, not the rule:
--   names:  ALL CAPS, stray whitespace, suffixes jammed into the last name,
--           middle names in the first-name field, 'LAST, FIRST' in one field,
--           FNU/LNU unknown-name placeholders, mojibake, apostrophes
--   phones: E.164, parens, dots, dashes, bare digits, extension text, and
--           garbage (placeholder text, truncated, empty); DISTINCT only
--           collapses byte-identical rows
--   types:  PhoneType is dirty too ('Cell', 'CELL PHONE') — the query's
--           case-sensitive IN ('CELL','MOBILE') silently misses those rows
--   misc:   courtroom code with no lookup row (CourtRoom comes back NULL),
--           empty judge name, trailing-space and off-format case numbers,
--           NULL FiledDate
-- All dialable numbers use the reserved 555-01XX range so no real number
-- can ever be texted.

SET search_path TO dbo, public;

INSERT INTO tblParty (PartyID, FirstName, LastName) VALUES
    (1,  'JAMES',      'MORENO'),       -- ALL CAPS entry
    (2,  'Tom',        'Becker Jr.'),   -- suffix jammed into last name
    (3,  ' Aisha',     'Clark '),       -- leading/trailing whitespace
    (4,  'ROBERT LEE', 'HALE'),         -- middle name in first-name field
    (5,  'Dana',       'Whitfield'),
    (6,  'LUIS',       'ORTEGA-DIAZ'),
    (7,  'Priya',      'Raman'),
    (8,  'NINA',       'SATO'),
    (9,  'Omar',       'Diallo'),
    (10, 'Grace',      'Lin'),
    (11, 'VICTOR M',   'NUNEZ'),
    (12, 'Marcus',     'Webb'),
    (13, 'FNU',        'LNU'),          -- First/Last Name Unknown placeholder
    (14, '',           'DOE, JANE'),    -- whole name in the last-name field
    (15, 'JosÃ©',      'O''Brien');     -- mojibake (José) + apostrophe

-- Scenario per case (IN/OUT = whether the reminder query returns it):
--   1 CR-2026-000101 Moreno    IN  1 row - hearing +7d; +30d jury trial excluded;
--                                  co-defendants Becker and DOE, JANE excluded
--                                  (not FirstDefendantID)
--   2 CR-2026-000102 Clark     IN  covers PhoneType 'MOBILE'
--   3 CR-2026-000103 Hale      OUT only a HOME phone; case number has a trailing space
--   4 CR-2026-000104 Whitfield IN  event exactly at CURRENT_DATE+7 00:00 (inclusive
--                                  lower bound); her second phone row has dirty
--                                  PhoneType 'Cell' and is silently missed
--   5 CR-2026-000105 Ortega    OUT event exactly at CURRENT_DATE+8 00:00 (exclusive
--                                  upper bound); NULL FiledDate
--   6 CR-2026-000106 Raman     OUT event +3d, outside window
--   7 CR-2026-000107 Sato      IN  2 rows - identical duplicate CELL rows collapse under
--                                  DISTINCT, but a format-variant entry of the SAME number
--                                  does not (the classic double-text bug)
--   8 CR-2026-000108 Diallo    IN  2 rows - distinct CELL and MOBILE numbers both
--                                  returned; co-defendant O'Brien excluded
--   9 CR-2026-000109 Lin       IN  daily status hearings +1..+14d keep the query
--                                  non-empty for a week after first start without a
--                                  db-reset; her 'CELL PHONE' row is silently missed
--  10 CR-2026-000110 Nunez     OUT no phone row; INNER JOIN drops the case
--  11 26CR000111     Webb      IN  3 rows - garbage numbers (placeholder text,
--                                  truncated, empty) flow into results; unmapped
--                                  courtroom code makes CourtRoom NULL; off-format
--                                  case number; co-defendant FNU LNU excluded
INSERT INTO tblCase (CaseID, CaseNumber, FirstDefendantID, FiledDate) VALUES
    (1,  'CR-2026-000101',  1,  CURRENT_DATE - 60),
    (2,  'CR-2026-000102',  3,  CURRENT_DATE - 45),
    (3,  'CR-2026-000103 ', 4,  CURRENT_DATE - 90),   -- trailing space
    (4,  'CR-2026-000104',  5,  CURRENT_DATE - 30),
    (5,  'CR-2026-000105',  6,  NULL),                -- filed date never entered
    (6,  'CR-2026-000106',  7,  CURRENT_DATE - 20),
    (7,  'CR-2026-000107',  8,  CURRENT_DATE - 75),
    (8,  'CR-2026-000108',  9,  CURRENT_DATE - 15),
    (9,  'CR-2026-000109',  10, CURRENT_DATE - 120),
    (10, 'CR-2026-000110',  11, CURRENT_DATE - 10),
    (11, '26CR000111',      12, CURRENT_DATE - 25);   -- older numbering format

INSERT INTO tblCaseParty (CaseID, PartyID, ConnectionType) VALUES
    (1, 1,  'DEFENDANT'),
    (1, 2,  'DEFENDANT'),   -- co-defendant, not FirstDefendantID: excluded by the join
    (1, 14, 'DEFENDANT'),   -- co-defendant with 'DOE, JANE' name
    (2, 3,  'DEFENDANT'),
    (3, 4,  'DEFENDANT'),
    (4, 5,  'DEFENDANT'),
    (5, 6,  'DEFENDANT'),
    (6, 7,  'DEFENDANT'),
    (7, 8,  'DEFENDANT'),
    (8, 9,  'DEFENDANT'),
    (8, 15, 'DEFENDANT'),   -- co-defendant with mojibake/apostrophe name
    (9, 10, 'DEFENDANT'),
    (10, 11, 'DEFENDANT'),
    (11, 12, 'DEFENDANT'),
    (11, 13, 'DEFENDANT');  -- co-defendant FNU LNU

INSERT INTO tblPartyPhone (PartyID, PhoneType, PhoneNumber) VALUES
    (1,  'CELL',       '(404) 555-0101'),        -- parens + space
    (2,  'CELL',       '404-555-0102'),
    (3,  'MOBILE',     '4045550103'),            -- bare 10 digits
    (4,  'HOME',       '404.555.0104'),          -- dotted; wrong phone type: excluded
    (5,  'CELL',       '+14045550105'),          -- clean E.164
    (5,  'Cell',       '404-555-0112'),          -- dirty type casing: silently missed
    (6,  'CELL',       '1-404-555-0106'),        -- leading country code, no plus
    (7,  'CELL',       '+1 (404) 555-0107'),     -- mixed styles
    (8,  'CELL',       '404-555-0108'),
    (8,  'CELL',       '404-555-0108'),          -- byte-identical dup: collapsed by DISTINCT
    (8,  'CELL',       '(404) 555-0108'),        -- SAME number, different format: NOT collapsed
    (9,  'CELL',       '404 555 0109'),          -- inner spaces
    (9,  'MOBILE',     '404-555-0110 ext. 12'),  -- extension text
    (10, 'CELL',       '404-555-0111'),
    (10, 'CELL PHONE', '(404) 555-0111'),        -- nonstandard type label: silently missed
    -- party 11 (Nunez) deliberately has no phone row
    (12, 'CELL',       'UNKNOWN'),               -- placeholder text instead of a number
    (12, 'CELL',       '5550134'),               -- truncated 7-digit local number
    (12, 'CELL',       '');                      -- empty string

INSERT INTO tblEvent (EventID, CourtRoomCode, JudgeName) VALUES
    (1, '1A',  'Judge Alvarez'),
    (2, '2B',  'Judge Brooks'),
    (3, '3C',  'Judge Chen'),
    (4, 'JC1', 'Judge Dawson'),
    (5, '2B',  'Judge Ellis'),
    (6, '9Z',  '');             -- no tblLookup row for '9Z' (CourtRoom resolves
                                -- to NULL); judge name never entered

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
    (10, 1, 1, (CURRENT_DATE + 7)  + time '14:00'),
    (11, 6, 1, (CURRENT_DATE + 7)  + time '15:00');  -- unmapped courtroom '9Z'

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
