-- Phase 1, Step 4: OCI GenAI credential + Select AI profile
--
-- CRITICAL LESSON: DBMS_CLOUD_AI defaults to us-chicago-1 for OCI GenAI.
-- Fix: use Resource Principal auth + "region":"uk-london-1" in profile JSON.
--
-- CRITICAL LESSON: "comments":"true" is required for the model to see table and
-- column COMMENTs. Without it the schema comments are never sent to the LLM, so
-- domain rules (e.g. cancellations are invoices where INVOICE_NO LIKE 'C%') are
-- ignored and the model invents wrong filters such as LIKE '%CANCELLED%'.
--
-- Run order:
--   PART A: as ADMIN        → enable resource principal
--   PART B: as NLQUERYUSER  → create profile

-- ============================================================
-- PART A — run as ADMIN
-- ============================================================

-- Enable resource principal for the database instance
EXEC DBMS_CLOUD_ADMIN.ENABLE_RESOURCE_PRINCIPAL();

-- Grant resource principal access to the app user
EXEC DBMS_CLOUD_ADMIN.ENABLE_RESOURCE_PRINCIPAL(username => 'NLQUERYUSER');

-- Verify
SELECT owner, credential_name FROM dba_credentials
WHERE credential_name = 'OCI$RESOURCE_PRINCIPAL';


-- ============================================================
-- PART B — run as NLQUERYUSER
-- ============================================================

BEGIN
  DBMS_CLOUD_AI.CREATE_PROFILE(
    profile_name => 'NL_QUERY_PROFILE',
    attributes   => '{
      "provider"          : "oci",
      "credential_name"   : "OCI$RESOURCE_PRINCIPAL",
      "model"             : "cohere.command-a-03-2025",
      "region"            : "uk-london-1",
      "comments"          : "true",
      "oci_compartment_id": "ocid1.tenancy.oc1..aaaaaaaazfq2ozmyhggult7w6klzhev3s6itnauhxdbdgazelea6hv3rtodq",
      "object_list"       : [
        {"owner": "NLQUERYUSER", "name": "CUSTOMERS"},
        {"owner": "NLQUERYUSER", "name": "PRODUCTS"},
        {"owner": "NLQUERYUSER", "name": "INVOICES"},
        {"owner": "NLQUERYUSER", "name": "INVOICE_LINES"}
      ]
    }'
  );
END;
/

-- Verify
SELECT profile_name, status FROM user_cloud_ai_profiles
WHERE profile_name = 'NL_QUERY_PROFILE';

-- Functional test (run as NLQUERYUSER)
SELECT DBMS_CLOUD_AI.GENERATE(
    prompt       => 'how many customers are there',
    profile_name => 'NL_QUERY_PROFILE',
    action       => 'showsql'
) AS generated_sql FROM DUAL;
-- Expected: SELECT COUNT(*) FROM CUSTOMERS

SELECT DBMS_CLOUD_AI.GENERATE(
    prompt       => 'how many customers are there',
    profile_name => 'NL_QUERY_PROFILE',
    action       => 'runsql'
) AS result FROM DUAL;
-- Expected: {"customer_count": 4372}
