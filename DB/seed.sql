PRAGMA foreign_keys = ON;


-- =========================
-- Countries
-- =========================
INSERT INTO Country (country_id, name, iso_code, region) VALUES
(1, 'Jordan', 'JO', 'Middle East'),
(2, 'Saudi Arabia', 'SA', 'Middle East'),
(3, 'UAE', 'AE', 'Middle East');

-- =========================
-- Departments
-- =========================
INSERT INTO Department (department_id, name) VALUES
(1, 'Financial Advisory'),
(2, 'Management Consulting'),
(3, 'Technology Consulting');

-- =========================
-- Sectors
-- =========================
INSERT INTO Sector (sector_id, name, description) VALUES
(1, 'Public Sector', 'Government and public institutions'),
(2, 'Financial Services', 'Banks and financial institutions');

-- =========================
-- Business Lines
-- =========================
INSERT INTO BusinessLine (business_line_id, name, description) VALUES
(1, 'Audit & Assurance', 'Audit services'),
(2, 'Advisory', 'Consulting services');

-- =========================
-- Languages
-- =========================
INSERT INTO Language (language_id, name, iso_code) VALUES
(1, 'Arabic', 'ar'),
(2, 'English', 'en');

-- =========================
-- Certifications
-- =========================
INSERT INTO Certification (certification_id, name, issuing_body) VALUES
(1, 'CPA', 'AICPA'),
(2, 'CFA', 'CFA Institute');







-- =========================
-- Employees
-- =========================
INSERT INTO Employee (
    employee_id,
    department_id,
    residence_country_id,
    first_name,
    last_name,
    email,
    phone,
    hire_date
) VALUES
(1, 1, 1, 'Ahmed', 'Al-Mansour', 'ahmed@bdo.com', '0790000000', '2018-01-15');

-- =========================
-- Subcontractors
-- =========================
INSERT INTO Subcontractor (
    subcontractor_id,
    residence_country_id,
    company_name,
    contact_name,
    email,
    phone
) VALUES
(1, 2, 'Gulf Advisory LLC', 'Khalid Omar', 'contact@gulfadvisory.com', '0500000000');








-- =========================
-- Resources
-- =========================
INSERT INTO Resource (
    resource_id,
    resource_type,
    employee_id,
    subcontractor_id,
    status,
    bio_text,
    cv_text,
    is_willing_to_travel
) VALUES
(1, 'Employee', 1, NULL, 'Active',
 'Senior financial consultant with public sector experience.',
 'Ahmed has 6+ years experience in advisory.',
 1),

(2, 'Subcontractor', NULL, 1, 'Active',
 'External advisory firm.',
 'Specialized in financial restructuring.',
 0);





-- =========================
-- Clients
-- =========================
INSERT INTO Client (client_id, name, contact_email, contact_phone) VALUES
(1, 'Ministry of Finance', 'info@mof.gov.jo', '065000000');

-- =========================
-- Projects
-- =========================
INSERT INTO Project (
    project_id,
    country_id,
    client_id,
    name,
    description,
    start_date,
    end_date
) VALUES
(1, 1, 1, 'Public Finance Reform',
 'Advisory project for public finance reform.',
 '2023-01-01',
 '2023-12-31');

-- =========================
-- Roles
-- =========================
INSERT INTO Role (role_id, name, description) VALUES
(1, 'Project Manager', 'Manages the project'),
(2, 'Senior Consultant', 'Executes core advisory work');






-- =========================
-- Assignments
-- =========================
INSERT INTO Assignment (
    assignment_id,
    resource_id,
    project_id,
    work_site_country_id,
    role_id,
    start_date,
    end_date,
    assignment_status
) VALUES
(1, 1, 1, 1, 2, '2023-01-01', '2023-12-31', 'Completed'),
(2, 2, 1, 1, 1, '2023-06-01', '2023-09-30', 'Completed');




-- =========================
-- Resource Languages
-- =========================
INSERT INTO ResourceLanguage (resource_id, language_id, proficiency_level) VALUES
(1, 1, 'Native'),
(1, 2, 'Fluent'),
(2, 2, 'Fluent');

-- =========================
-- Resource Certifications
-- =========================
INSERT INTO ResourceCertification (
    resource_id,
    certification_id,
    obtained_date,
    expiry_date
) VALUES
(1, 1, '2017-05-01', NULL);

-- =========================
-- Project Business Lines
-- =========================
INSERT INTO ProjectBusinessLine (project_id, business_line_id, primary_flag) VALUES
(1, 2, 1);

-- =========================
-- Client Sectors
-- =========================
INSERT INTO ClientSector (client_id, sector_id, primary_flag) VALUES
(1, 1, 1);





-- =========================
-- Notes
-- =========================
INSERT INTO Notes (
    note_id,
    entity_type,
    entity_id,
    note_text,
    created_by,
    visibility,
    is_flagged
) VALUES
(1, 'Project', 1, 'Client requested accelerated delivery.', 'Admin', 'Internal', 1),
(2, 'Employee', 1, 'Strong performer on public sector engagements.', 'Admin', 'Internal', 0),
(3, 'Assignment', 1, 'Delivered ahead of schedule.', 'Admin', 'Internal', 0);
