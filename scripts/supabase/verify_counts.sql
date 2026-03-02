SELECT 'audits' AS table_name, count(*) AS row_count FROM audits
UNION ALL
SELECT 'reports', count(*) FROM reports
UNION ALL
SELECT 'audited_pages', count(*) FROM audited_pages
UNION ALL
SELECT 'competitors', count(*) FROM competitors
ORDER BY table_name;
