-- 001_add_employee_hr_fields.sql
ALTER TABLE Employee ADD COLUMN birth_date DATE;
ALTER TABLE Employee ADD COLUMN title TEXT;
ALTER TABLE Employee ADD COLUMN years_experience INTEGER;
