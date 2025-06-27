# TerryFox LIMS

A custom Laboratory Information Management System (LIMS) for the TerryFox project. This system allows tracking of projects, cases, and their associated data such as sequencing status, coverage information, and accession numbers.

## Features

- Project management with dedicated Project Lead tracking and management
- Case tracking with status monitoring
- Coverage information (RNA, DNA-T, DNA-N)
- Tier classification (A, B, FAIL)
- Accession number management
- Comment system for cases
- Search and filter functionality for projects and cases
- Role-based permissions (Admin, PI, Bioinformatician)
- Comprehensive statistics at global and project levels
- Batch case creation for adding multiple cases at once
- CSV import for creating and updating cases
- Beautiful and user-friendly interface
- Production-ready deployment with Gunicorn
- Secure authentication flows (login/logout)
- HTTPS support with IP address (10.220.115.67) and localhost access

## Overview

   ![Overview on the Project](overview.png)

## Requirements

- Python 3.8+
- Django 5.0+
- Conda environment with Django installed
- Additional packages (see requirements.txt):
  - django-crispy-forms and crispy-bootstrap5 for enhanced form rendering
  - gunicorn for production deployment
  - whitenoise for static file serving
  - python-decouple for environment variable management
  - django-extensions, werkzeug, and pyOpenSSL for HTTPS support

## Installation

### Prerequisites
- Python 3.8+
- Git

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/acri-nb/terryfox-lims.git
   cd terryfox-lims
   ```

2. Choose one of the following installation methods:

#### Option A: Using pip (recommended)
   ```bash
   # Create and activate a virtual environment (optional but recommended)
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   
   # Install dependencies from requirements.txt
   pip install -r requirements.txt
   ```

#### Option B: Using Conda
   ```bash
   # Create and activate a Conda environment
   conda create -n terryfox python=3.9
   conda activate terryfox
   
   # Install dependencies
   pip install -r requirements.txt
   ```

3. Run migrations to set up the database:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

4. Create a superuser account:
   ```bash
   python manage.py createsuperuser
   ```

5. Run the development server:
   ```bash
   python manage.py runserver
   ```

6. Visit `http://127.0.0.1:8000/` to access the application
   - For admin access, go to `http://127.0.0.1:8000/admin/`
   - Use the admin panel to create required user groups:
     - Create "PI" group (Read-only access)
     - Create "Bioinformatician" group (CRUD access)
     - Assign users to these groups

## Production Deployment

For production deployment, we've included several tools and configuration files:

1. Install production dependencies:
   ```bash
   pip install -r requirements.txt
   pip install django-extensions werkzeug pyOpenSSL  # For HTTPS support
   ```

2. Check production configuration:
   ```bash
   python check_production.py
   ```

3. Start the application in production mode (now with HTTPS by default):
   ```bash
   sudo ./start_production_debug.sh
   ```
   
   This will automatically:
   - Generate self-signed SSL certificates if they don't exist (including for IP 10.220.115.67)
   - Set up Django with secure HTTPS settings
   - Start the server on port 443 (standard HTTPS port) with SSL enabled
   - Requires root privileges (sudo) because it uses port 443

4. (Optional) Alternative HTTPS options:
   ```bash
   # For Nginx-based HTTPS setup (requires Nginx installed)
   sudo ./setup_nginx_production.sh
   ```

5. (Recommended) Configure as a systemd service for permanent operation:
   ```bash
   # Create a systemd service file
   sudo nano /etc/systemd/system/terryfox-lims.service
   ```
   
   Add the following content to the file:
   ```ini
   [Unit]
   Description=TerryFox LIMS Service
   After=network.target
   
   [Service]
   User=root
   Group=root
   WorkingDirectory=/home/hadriengt/project/lims/terryfox-lims
   ExecStart=/home/hadriengt/project/lims/terryfox-lims/start_production_debug.sh
   Restart=always
   RestartSec=10
   StandardOutput=journal
   StandardError=journal
   SyslogIdentifier=terryfox-lims
   
   [Install]
   WantedBy=multi-user.target
   ```
   
   Then enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable terryfox-lims.service
   sudo systemctl start terryfox-lims.service
   ```
   
   This ensures the LIMS will:
   - Run continuously in the background
   - Restart automatically if it crashes
   - Start automatically when the server boots
   - Be manageable via systemctl commands

The application will be available at:
- HTTPS (Default): https://10.220.115.67:443 or https://localhost:443

**Note**: When accessing the application, your browser will show a security warning because of the self-signed certificate. This is normal and expected. You can safely proceed by accepting the certificate exception.

For more detailed instructions and advanced configuration options:
- Refer to `PRODUCTION.md` for general production setup
- See "Option C: Direct HTTPS with Django" in PRODUCTION.md for details on the current HTTPS implementation

## User Roles

- **Superuser/Admin**: Full access to all features and admin panel
- **PI (Principal Investigator)**: Read-only access to view projects, project leads, and cases
- **Bioinformatician**: Full CRUD permissions on projects, project leads, and cases

## Project Statistics

The LIMS provides detailed statistics at two levels:

1. **Global statistics** (Home page):
   - Total number of projects
   - Projects by Project Lead
   - Total number of cases
   - Cases by status (Received, Library Prepped, Transferred to NFL, Bioinfo Analysis, Completed)
   - Cases by tier (A, B, FAIL)

2. **Project-specific statistics** (Project detail page):
   - Project Lead information
   - Total cases in the project
   - Cases by status
   - Cases by tier

## Usage

1. Login with your user credentials
2. From the dashboard, you can see all projects and global statistics
3. Use the search box to filter projects by name or project lead
4. Click on "Project Leads" button to manage project leads (create, edit, delete)
5. Click on a project to view its details, statistics, and associated cases
6. Use the search and filter options to find specific cases by name, status, or tier
7. Click on a case to view its details, including status, coverage information, and accession numbers
8. Bioinformaticians can create, edit, and delete projects, project leads, and cases
9. PIs can view all information but cannot make changes

## Project Lead Management

The system provides a dedicated interface for managing Project Leads:

1. Access the Project Leads management by clicking the "Project Leads" button on the home page
2. View all existing project leads and the number of projects they manage
3. Create new project leads by clicking "New Project Lead"
4. Edit existing project leads by clicking the edit icon
5. Delete project leads that aren't associated with any projects
6. When creating or editing a project, select a project lead from the dropdown menu

## Search and Filter Features

The system provides search and filter capabilities to help you quickly find what you need:

### Project Filtering (Home Page)
- **Project Name**: Search for projects by entering part of their name
- **Project Lead**: Filter projects to show only those managed by a specific project lead
- Filter results update immediately when you click the "Filter" button
- A "Clear" button allows you to reset all filters

### Case Filtering (Project Detail Page)
- **Case Name**: Search for cases by entering part of their name
- **Status**: Filter cases by their current status (Received, Library Prepped, Transferred to NFL, etc.)
- **Tier**: Filter cases by their tier classification (A, B, FAIL)
- Visual indicators show when filters are active and how many results match

### Batch Case Creation

The system allows users with CRUD permissions (Bioinformaticians and Administrators) to add multiple cases to a project at once:

- Access the batch creation by clicking "Add Cases in Batch" on the project detail page
- Specify the **batch name** that will be used as a prefix for all case names
- Set the **first case number** (where the numbering will start)
- Set the **last case number** (where the numbering will end)
- Set the **default values** that will be applied to all cases in the batch (status, coverage values)

Cases are created with names following the pattern `{batch_name}-{number}`. For example, if you enter "Lung" as the batch name, 5 as the first case number, and 7 as the last case number, the system will create cases named "Lung-5", "Lung-6", and "Lung-7".

At least 2 cases must be created in a batch. This feature is particularly useful when processing sample batches from the same experiment or tissue type.

### CSV Case Import

The system allows users with CRUD permissions (Bioinformaticians and Administrators) to import multiple cases from a CSV file:

- Access the CSV import by clicking "Add Cases with CSV" on the project detail page
- Upload a CSV file following the required format with these headers:
  - **CaseID**: The unique identifier for the case
  - **Status**: The status of the case (must match system values)
  - **DNAT**: DNA Tumor Coverage value
  - **DNAN**: DNA Normal Coverage value
  - **RNA**: RNA Coverage value
- The system will automatically:
  - Create new cases for entries that don't exist yet
  - Update existing cases with the new data
  - Display a summary of how many cases were created and updated

A template CSV file is available for download on the import page to help users get started. This feature is particularly useful for importing data from other systems or for bulk updates to existing cases.

## Development

This project follows standard Django application architecture:

- `core/models.py`: Database models (ProjectLead, Project, Case, etc.)
- `core/views.py`: View functions for all CRUD operations
- `core/forms.py`: Forms for data input
- `core/admin.py`: Admin interface configuration
- `core/templatetags/`: Custom template tags and filters
- `templates/`: HTML templates
- `static/`: Static files (CSS, JS, images)

## License

ACRI - Atlantic Cancer Research Institute

## Contact

For any questions or support, please contact the development team. 