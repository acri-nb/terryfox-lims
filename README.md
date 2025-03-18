# TerryFox LIMS

A custom Laboratory Information Management System (LIMS) for the TerryFox project. This system allows tracking of projects, cases, and their associated data such as sequencing status, coverage information, and accession numbers.

## Features

- Project management
- Case tracking with status monitoring
- Coverage information (RNA, DNA-T, DNA-N)
- Tier classification (A, B, FA)
- Accession number management
- Comment system for cases
- Role-based permissions (Admin, PI, Bioinformatician)
- Beautiful and user-friendly interface

## Screenshots

*(Screenshots will appear here once the application is deployed)*

## Requirements

- Python 3.8+
- Django 5.0+
- Conda environment with Django installed

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd terryfox
   ```

2. Activate the Conda environment:
   ```
   conda activate django
   ```

3. Install required packages:
   ```
   pip install django crispy-forms crispy-bootstrap5
   ```

4. Run migrations:
   ```
   python manage.py makemigrations
   python manage.py migrate
   ```

5. Create a superuser:
   ```
   python manage.py createsuperuser
   ```

6. Run the development server:
   ```
   python manage.py runserver
   ```

7. Visit `http://127.0.0.1:8000/admin/` to access the admin panel and create user groups:
   - Create "PI" group
   - Create "Bioinformatician" group
   - Assign users to these groups

## User Roles

- **Superuser/Admin**: Full access to all features and admin panel
- **PI (Principal Investigator)**: Full CRUD permissions on projects and cases
- **Bioinformatician**: Read-only access to all information

## Usage

1. Login with your user credentials
2. From the dashboard, you can see all projects
3. Click on a project to view its cases
4. Click on a case to view its details, including status, coverage information, and accession numbers
5. PI users can create, edit, and delete projects and cases
6. Bioinformaticians can view all information but cannot make changes

## Development

This project follows standard Django application architecture:

- `core/models.py`: Database models
- `core/views.py`: View functions
- `core/forms.py`: Forms for data input
- `core/admin.py`: Admin interface configuration
- `templates/`: HTML templates
- `static/`: Static files (CSS, JS, images)

## License

© IARC - International Agency for Research on Cancer

## Contact

For any questions or support, please contact the development team. 