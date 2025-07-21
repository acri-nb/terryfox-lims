import os
import django
import random
import string

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'terryfox_lims.settings')
django.setup()

from django.contrib.auth.models import User, Group

# Liste des utilisateurs (Nom Complet)
users = [
    "Tom Belbin",
    "Flora Machovsky",
    "Juanni Liu",
    "Jorge Pinzon",
    "Riley Arseneau",
    "Louisa Larissa",
    "Daniel Loos",
]

def username_from_name(fullname):
    parts = fullname.strip().split()
    if len(parts) == 1:
        return parts[0].lower()
    else:
        return f"{parts[0].lower()}{parts[1][0].lower()}"

def random_password(length=12):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

def main():
    viewer_group, _ = Group.objects.get_or_create(name='viewer')
    credentials = []
    for fullname in users:
        username = username_from_name(fullname)
        password = random_password()
        user, created = User.objects.get_or_create(username=username, defaults={
            'first_name': fullname.split()[0],
            'last_name': ' '.join(fullname.split()[1:]),
        })
        if created:
            user.set_password(password)
            user.save()
            user.groups.add(viewer_group)
            credentials.append(f"{username}:{password}")
        else:
            credentials.append(f"{username}:EXISTING")
    # Écriture dans le fichier user_pass.txt
    with open('user_pass.txt', 'w') as f:
        for line in credentials:
            f.write(line + '\n')
    print("Utilisateurs créés et mots de passe enregistrés dans user_pass.txt")

if __name__ == '__main__':
    main() 