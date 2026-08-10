-- Postgres translation of the production Odyssey T-SQL reminder query:
-- upcoming hearings exactly 7 days out, for first defendants with a cell phone.
--
-- Deltas from prod: WITH(NOLOCK) dropped, DATEADD(d,N,CONVERT(DATE,GETDATE()))
-- rewritten as CURRENT_DATE + N, and an ORDER BY added for stable output.
-- Identifiers and dbo.fnGetLookupDescription run as in prod.
SELECT DISTINCT
    c.CaseID,
    cp.CasePartyID,
    c.CaseNumber,
    et.EventTypeDescription,
    ce.CaseStartDateTime AS EventDateTime,
    dbo.fnGetLookupDescription(e.CourtRoomCode, 'CourtRoom') AS CourtRoom,
    pp.PhoneType,
    pp.PhoneNumber
FROM tblCase c
INNER JOIN tblCaseParty cp
    ON c.CaseID = cp.CaseID AND c.FirstDefendantID = cp.PartyID
INNER JOIN tblPartyPhone pp
    ON cp.PartyID = pp.PartyID
INNER JOIN tblCaseEvent ce
    ON c.CaseID = ce.CaseID
INNER JOIN tblEvent e
    ON ce.EventID = e.EventID
INNER JOIN tblEventType et
    ON ce.CaseEventTypeID = et.EventTypeID
WHERE
    ce.CaseStartDateTime >= CURRENT_DATE + 7
    AND ce.CaseStartDateTime < CURRENT_DATE + 8
    AND pp.PhoneType IN ('CELL', 'MOBILE')
ORDER BY EventDateTime, CaseNumber;
