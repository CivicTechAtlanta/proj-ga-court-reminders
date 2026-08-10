-- Stable reference data: courtroom lookup codes and event types.

SET search_path TO dbo, public;

INSERT INTO tblLookup (LookupType, LookupCode, LookupDescription) VALUES
    ('CourtRoom', '1A',  'Courtroom 1A - Main Courthouse, Floor 1'),
    ('CourtRoom', '2B',  'Courtroom 2B - Main Courthouse, Floor 2'),
    ('CourtRoom', '3C',  'Courtroom 3C - Main Courthouse, Floor 3'),
    ('CourtRoom', 'JC1', 'Justice Center Courtroom 1');

INSERT INTO tblEventType (EventTypeID, EventTypeCode, EventTypeDescription) VALUES
    (1, 'ARRAIGN', 'Arraignment'),
    (2, 'STATUS',  'Status Hearing'),
    (3, 'PRELIM',  'Preliminary Hearing'),
    (4, 'BENCH',   'Bench Trial'),
    (5, 'JURY',    'Jury Trial');
