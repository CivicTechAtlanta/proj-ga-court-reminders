-- SQL Server schema for the court case database: the native form of the
-- Postgres translation in db/init/01-schema.sql (see ADR 002). Keep the two
-- in step; the reminder query must run near-verbatim against both.
--
-- Rerunnable: everything it creates is dropped first, in dependency order.
-- Batches are separated by GO lines (court_db/seed.py splits on them);
-- CREATE FUNCTION must be the only statement in its batch.

DROP TABLE IF EXISTS dbo.tblCaseEvent;
DROP TABLE IF EXISTS dbo.tblPartyPhone;
DROP TABLE IF EXISTS dbo.tblCaseParty;
DROP TABLE IF EXISTS dbo.tblCase;
DROP TABLE IF EXISTS dbo.tblEvent;
DROP TABLE IF EXISTS dbo.tblEventType;
DROP TABLE IF EXISTS dbo.tblParty;
DROP FUNCTION IF EXISTS dbo.fnGetLookupDescription;
DROP TABLE IF EXISTS dbo.tblLookup;
GO

-- Generic code/description lookup, resolved in prod via dbo.fnGetLookupDescription
CREATE TABLE dbo.tblLookup (
    LookupType        nvarchar(50)  NOT NULL,
    LookupCode        nvarchar(50)  NOT NULL,
    LookupDescription nvarchar(255) NOT NULL,
    PRIMARY KEY (LookupType, LookupCode)
);
GO

-- Argument order matches the prod call site: dbo.fnGetLookupDescription(code, type)
CREATE FUNCTION dbo.fnGetLookupDescription(@code nvarchar(50), @type nvarchar(50))
RETURNS nvarchar(255)
AS
BEGIN
    RETURN (
        SELECT LookupDescription
        FROM dbo.tblLookup
        WHERE LookupCode = @code AND LookupType = @type
    );
END;
GO

CREATE TABLE dbo.tblParty (
    PartyID   int IDENTITY(1,1) PRIMARY KEY,
    FirstName nvarchar(100) NOT NULL,
    LastName  nvarchar(100) NOT NULL
);

CREATE TABLE dbo.tblCase (
    CaseID           int IDENTITY(1,1) PRIMARY KEY,
    CaseNumber       nvarchar(50) NOT NULL UNIQUE,
    FirstDefendantID int NOT NULL REFERENCES dbo.tblParty (PartyID),
    CaseType         nvarchar(50) NOT NULL DEFAULT 'CRIMINAL',
    FiledDate        date NULL
);

CREATE TABLE dbo.tblCaseParty (
    CasePartyID    int IDENTITY(1,1) PRIMARY KEY,
    CaseID         int NOT NULL REFERENCES dbo.tblCase (CaseID),
    PartyID        int NOT NULL REFERENCES dbo.tblParty (PartyID),
    ConnectionType nvarchar(50) NOT NULL DEFAULT 'DEFENDANT',
    UNIQUE (CaseID, PartyID)
);

-- No unique constraint on (PartyID, PhoneType, PhoneNumber) and no CHECK on
-- PhoneType: prod data has duplicate rows and dirty type labels, and the
-- fixtures seed both on purpose (see db/init/01-schema.sql).
CREATE TABLE dbo.tblPartyPhone (
    PartyPhoneID int IDENTITY(1,1) PRIMARY KEY,
    PartyID      int NOT NULL REFERENCES dbo.tblParty (PartyID),
    PhoneType    nvarchar(50)  NOT NULL,
    PhoneNumber  nvarchar(50)  NOT NULL
);

CREATE TABLE dbo.tblEventType (
    EventTypeID          int IDENTITY(1,1) PRIMARY KEY,
    EventTypeCode        nvarchar(50)  NOT NULL UNIQUE,
    EventTypeDescription nvarchar(100) NOT NULL
);

-- A scheduled court session / calendar block; CourtRoomCode resolves through
-- tblLookup rows with LookupType = 'CourtRoom'
CREATE TABLE dbo.tblEvent (
    EventID       int IDENTITY(1,1) PRIMARY KEY,
    CourtRoomCode nvarchar(50) NOT NULL,
    JudgeName     nvarchar(100) NULL
);

-- Mirrors the prod quirk that the event type hangs off tblCaseEvent
-- (CaseEventTypeID), not tblEvent. CaseStartDateTime is court-local time.
CREATE TABLE dbo.tblCaseEvent (
    CaseEventID       int IDENTITY(1,1) PRIMARY KEY,
    CaseID            int NOT NULL REFERENCES dbo.tblCase (CaseID),
    EventID           int NOT NULL REFERENCES dbo.tblEvent (EventID),
    CaseEventTypeID   int NOT NULL REFERENCES dbo.tblEventType (EventTypeID),
    CaseStartDateTime datetime NOT NULL
);

CREATE INDEX idx_tblCaseEvent_start ON dbo.tblCaseEvent (CaseStartDateTime);
GO
