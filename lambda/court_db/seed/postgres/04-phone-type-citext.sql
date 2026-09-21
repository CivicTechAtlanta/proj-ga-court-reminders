-- Make tblPartyPhone.PhoneType case-insensitive, as it is in production.
--
-- Prod's SQL Server compares strings under a case-insensitive collation
-- (SQL_Latin1_General_CP1_CI_AS), so the reminder query's IN ('CELL','MOBILE')
-- matches a row typed 'Cell' as well. Postgres text compares case-sensitively
-- and would skip it, and PhoneType is the one column whose comparison decides
-- who gets texted: plain text would hide a person here who is reminded in
-- production. citext reproduces the prod collation for =, IN, DISTINCT and
-- LIKE alike, and still stores and returns the original casing. See ADR 002.
--
-- Postgres only: SQL Server is already case-insensitive, so seed/sqlserver/
-- has no counterpart. Runs after the fixtures load; the ALTER converts the
-- loaded rows through citext's assignment cast from text, inside the same
-- transaction as the rest of the seed.

SET search_path TO dbo, public;

-- In public, so a re-seed's DROP SCHEMA dbo (01-schema.sql) leaves it alone.
CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA public;

ALTER TABLE tblPartyPhone ALTER COLUMN PhoneType TYPE citext;
