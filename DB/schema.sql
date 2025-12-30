PRAGMA foreign_keys = ON;

-- =========================
-- Reference Tables
-- =========================

CREATE TABLE Country (
    country_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    iso_code TEXT,
    region TEXT
);

CREATE TABLE Department (
    department_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE Sector (
    sector_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE BusinessLine (
    business_line_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE Language (
    language_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    iso_code TEXT
);

CREATE TABLE Certification (
    certification_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    --issuing_body TEXT--  legacy, do not use (kept for backward compatibility)
);

-- =========================
-- People Tables
-- =========================

CREATE TABLE Employee (
    employee_id INTEGER PRIMARY KEY,
    department_id INTEGER,
    residence_country_id INTEGER,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    hire_date DATE,
    birth_date DATE,
    title TEXT,
    years_experience INTEGER,

    FOREIGN KEY (department_id) REFERENCES Department(department_id),
    FOREIGN KEY (residence_country_id) REFERENCES Country(country_id)
);

CREATE TABLE Subcontractor (
    subcontractor_id INTEGER PRIMARY KEY,
    residence_country_id INTEGER,
    company_name TEXT,
    contact_name TEXT,
    email TEXT,
    phone TEXT,
    birth_date DATE,
    title TEXT,
    years_experience INTEGER,
    FOREIGN KEY (residence_country_id) REFERENCES Country(country_id)
);

CREATE TABLE Resource (
    resource_id INTEGER PRIMARY KEY,
    resource_type TEXT CHECK (resource_type IN ('Employee', 'Subcontractor')),
    employee_id INTEGER,
    subcontractor_id INTEGER,
    status TEXT,
    bio_text TEXT,
    cv_text TEXT,
    is_willing_to_travel INTEGER DEFAULT 0,
    FOREIGN KEY (employee_id) REFERENCES Employee(employee_id),
    FOREIGN KEY (subcontractor_id) REFERENCES Subcontractor(subcontractor_id),
    CHECK (
        (employee_id IS NOT NULL AND subcontractor_id IS NULL) OR
        (employee_id IS NULL AND subcontractor_id IS NOT NULL)
    )
);

-- =========================
-- Business Core Tables
-- =========================

CREATE TABLE Client (
    client_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    contact_email TEXT,
    contact_phone TEXT
);

CREATE TABLE Project (
    project_id INTEGER PRIMARY KEY,
    country_id INTEGER,
    client_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    start_date DATE,
    end_date DATE,
    FOREIGN KEY (country_id) REFERENCES Country(country_id),
    FOREIGN KEY (client_id) REFERENCES Client(client_id)
);

CREATE TABLE Role (
    role_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE Assignment (
    assignment_id INTEGER PRIMARY KEY,
    resource_id INTEGER,
    project_id INTEGER,
    work_site_country_id INTEGER,
    role_id INTEGER,
    start_date DATE,
    end_date DATE,
    assignment_status TEXT,
    FOREIGN KEY (resource_id) REFERENCES Resource(resource_id),
    FOREIGN KEY (project_id) REFERENCES Project(project_id),
    FOREIGN KEY (work_site_country_id) REFERENCES Country(country_id),
    FOREIGN KEY (role_id) REFERENCES Role(role_id)
);

-- =========================
-- Junction Tables
-- =========================

CREATE TABLE ResourceLanguage (
    resource_id INTEGER,
    language_id INTEGER,
    proficiency_level TEXT,
    PRIMARY KEY (resource_id, language_id),
    FOREIGN KEY (resource_id) REFERENCES Resource(resource_id),
    FOREIGN KEY (language_id) REFERENCES Language(language_id)
);

CREATE TABLE ResourceCertification (
    resource_id INTEGER,
    certification_id INTEGER,
    obtained_date DATE,
    expiry_date DATE,
    issuing_body TEXT,
    PRIMARY KEY (resource_id, certification_id),
    FOREIGN KEY (resource_id) REFERENCES Resource(resource_id),
    FOREIGN KEY (certification_id) REFERENCES Certification(certification_id)
);

CREATE TABLE ProjectBusinessLine (
    project_id INTEGER,
    business_line_id INTEGER,
    primary_flag INTEGER DEFAULT 0,
    PRIMARY KEY (project_id, business_line_id),
    FOREIGN KEY (project_id) REFERENCES Project(project_id),
    FOREIGN KEY (business_line_id) REFERENCES BusinessLine(business_line_id)
);

CREATE TABLE ClientSector (
    client_id INTEGER,
    sector_id INTEGER,
    primary_flag INTEGER DEFAULT 0,
    PRIMARY KEY (client_id, sector_id),
    FOREIGN KEY (client_id) REFERENCES Client(client_id),
    FOREIGN KEY (sector_id) REFERENCES Sector(sector_id)
);

-- =========================
-- Notes
-- =========================

CREATE TABLE Notes (
    note_id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    note_text TEXT NOT NULL,
    created_by TEXT NOT NULL,
    visibility TEXT NOT NULL,
    is_flagged INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at DATE
);


