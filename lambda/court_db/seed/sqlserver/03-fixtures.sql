-- Synthetic case data, row for row the same as db/init/03-fixtures.sql, which
-- documents every scenario and the deliberately dirty data quality.
-- Expected reminder-query result right after loading: exactly 11 rows.
--
-- Event dates are anchored to the server's GETDATE() at load time, so the
-- 7-days-out window matches immediately; rerun the loader to re-anchor.
-- One batch: the @today/@base variables are scoped to it.

DECLARE @today date = CAST(GETDATE() AS date);
DECLARE @base datetime = CAST(@today AS datetime);

SET IDENTITY_INSERT dbo.tblParty ON;
INSERT INTO dbo.tblParty (PartyID, FirstName, LastName) VALUES
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
    (15, N'JosÃ©',     'O''Brien');     -- mojibake (José) + apostrophe
SET IDENTITY_INSERT dbo.tblParty OFF;

SET IDENTITY_INSERT dbo.tblCase ON;
INSERT INTO dbo.tblCase (CaseID, CaseNumber, FirstDefendantID, FiledDate) VALUES
    (1,  'CR-2026-000101',  1,  DATEADD(day, -60,  @today)),
    (2,  'CR-2026-000102',  3,  DATEADD(day, -45,  @today)),
    (3,  'CR-2026-000103 ', 4,  DATEADD(day, -90,  @today)),   -- trailing space
    (4,  'CR-2026-000104',  5,  DATEADD(day, -30,  @today)),
    (5,  'CR-2026-000105',  6,  NULL),                        -- filed date never entered
    (6,  'CR-2026-000106',  7,  DATEADD(day, -20,  @today)),
    (7,  'CR-2026-000107',  8,  DATEADD(day, -75,  @today)),
    (8,  'CR-2026-000108',  9,  DATEADD(day, -15,  @today)),
    (9,  'CR-2026-000109',  10, DATEADD(day, -120, @today)),
    (10, 'CR-2026-000110',  11, DATEADD(day, -10,  @today)),
    (11, '26CR000111',      12, DATEADD(day, -25,  @today));   -- older numbering format
SET IDENTITY_INSERT dbo.tblCase OFF;

INSERT INTO dbo.tblCaseParty (CaseID, PartyID, ConnectionType) VALUES
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

INSERT INTO dbo.tblPartyPhone (PartyID, PhoneType, PhoneNumber) VALUES
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

SET IDENTITY_INSERT dbo.tblEvent ON;
INSERT INTO dbo.tblEvent (EventID, CourtRoomCode, JudgeName) VALUES
    (1, '1A',  'Judge Alvarez'),
    (2, '2B',  'Judge Brooks'),
    (3, '3C',  'Judge Chen'),
    (4, 'JC1', 'Judge Dawson'),
    (5, '2B',  'Judge Ellis'),
    (6, '9Z',  '');             -- no tblLookup row for '9Z' (CourtRoom resolves
                                -- to NULL); judge name never entered
SET IDENTITY_INSERT dbo.tblEvent OFF;

-- datetime + datetime adds the time-of-day literal (relative to 1900-01-01)
-- to the anchored date, the T-SQL equivalent of Postgres date + time.
-- CaseEventTypeID: 1=ARRAIGN 2=STATUS 3=PRELIM 4=BENCH 5=JURY (02-reference-data.sql)
INSERT INTO dbo.tblCaseEvent (CaseID, EventID, CaseEventTypeID, CaseStartDateTime) VALUES
    (1,  1, 1, DATEADD(day, 7,  @base) + CAST('09:00' AS datetime)),
    (1,  5, 5, DATEADD(day, 30, @base) + CAST('09:00' AS datetime)),  -- outside window: excluded
    (2,  2, 3, DATEADD(day, 7,  @base) + CAST('13:30' AS datetime)),
    (3,  1, 2, DATEADD(day, 7,  @base) + CAST('10:00' AS datetime)),
    (4,  3, 1, DATEADD(day, 7,  @base) + CAST('00:00' AS datetime)),  -- inclusive lower bound
    (5,  3, 1, DATEADD(day, 8,  @base) + CAST('00:00' AS datetime)),  -- exclusive upper bound: excluded
    (6,  2, 2, DATEADD(day, 3,  @base) + CAST('09:30' AS datetime)),  -- outside window: excluded
    (7,  1, 3, DATEADD(day, 7,  @base) + CAST('10:15' AS datetime)),
    (8,  2, 4, DATEADD(day, 7,  @base) + CAST('11:00' AS datetime)),
    (10, 1, 1, DATEADD(day, 7,  @base) + CAST('14:00' AS datetime)),
    (11, 6, 1, DATEADD(day, 7,  @base) + CAST('15:00' AS datetime));  -- unmapped courtroom '9Z'

-- Lin's daily status hearings, +1..+14 days out
INSERT INTO dbo.tblCaseEvent (CaseID, EventID, CaseEventTypeID, CaseStartDateTime)
SELECT 9, 4, 2, DATEADD(day, n, @base) + CAST('08:30' AS datetime)
FROM (VALUES (1), (2), (3), (4), (5), (6), (7), (8), (9), (10), (11), (12), (13), (14)) AS s(n);
GO
