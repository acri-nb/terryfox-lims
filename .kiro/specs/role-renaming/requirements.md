# Requirements Document

## Introduction

This feature involves renaming user roles throughout the TerryFox LIMS system to improve clarity and consistency. The current role names "PI" and "Bioinformatician" will be changed to "viewer" and "editor" respectively. This change must be applied consistently across all parts of the system including backend code, frontend templates, documentation, and any configuration files.

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want the user roles to have clear, descriptive names so that their permissions and purpose are immediately understood.

#### Acceptance Criteria

1. WHEN the system is updated THEN the role "PI" SHALL be renamed to "viewer"
2. WHEN the system is updated THEN the role "Bioinformatician" SHALL be renamed to "editor"
3. WHEN users access the system THEN they SHALL see the new role names in all user interfaces
4. WHEN administrators manage user permissions THEN they SHALL use the new role names
5. WHEN the system documentation is reviewed THEN it SHALL reflect the new role names consistently

### Requirement 2

**User Story:** As a developer maintaining the system, I want all code references to use the new role names so that the codebase is consistent and maintainable.

#### Acceptance Criteria

1. WHEN reviewing Python code THEN all references to "PI" SHALL be changed to "viewer"
2. WHEN reviewing Python code THEN all references to "Bioinformatician" SHALL be changed to "editor"
3. WHEN reviewing template files THEN all role name references SHALL use the new names
4. WHEN reviewing JavaScript code THEN all role name references SHALL use the new names
5. WHEN reviewing CSS or styling THEN any role-specific classes SHALL use the new names

### Requirement 3

**User Story:** As an existing user of the system, I want my current permissions to remain unchanged after the role renaming so that I can continue working without disruption.

#### Acceptance Criteria

1. WHEN the role renaming is applied THEN existing user group memberships SHALL be preserved
2. WHEN users log in after the update THEN their permissions SHALL remain identical to before
3. WHEN the database is updated THEN existing group records SHALL be renamed without data loss
4. WHEN the system starts after the update THEN all permission checks SHALL work with the new role names

### Requirement 4

**User Story:** As a system administrator, I want the documentation to accurately reflect the new role names so that I can properly manage user access and understand system functionality.

#### Acceptance Criteria

1. WHEN reviewing system documentation THEN all references to "PI" SHALL be updated to "viewer"
2. WHEN reviewing system documentation THEN all references to "Bioinformatician" SHALL be updated to "editor"
3. WHEN reviewing code comments THEN role name references SHALL use the new names
4. WHEN reviewing README files THEN role descriptions SHALL use the new names
5. WHEN reviewing configuration examples THEN they SHALL demonstrate the new role names