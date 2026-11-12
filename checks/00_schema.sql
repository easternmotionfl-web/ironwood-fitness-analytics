-- All raw tables and their columns
select table_name, column_name, data_type
from information_schema.columns
where table_schema = 'raw'
order by table_name, ordinal_position;