import bcrypt
from backend.models.db import users

# Fix: store as 'password_hash' (string), and ensure 'name' field exists
new_password = 'admin123'
pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

result = users().update_one(
    {'email': 'admin@paperiq.local'},
    {'$set': {
        'password_hash': pw_hash,
        'name': 'Admin',
    },
    '$unset': {'password': ''}  # remove old wrong field if it exists
    }
)
print(f'Updated: {result.modified_count} user')

# Verify stored document
u = users().find_one({'email': 'admin@paperiq.local'}, {'email': 1, 'name': 1, 'role': 1, 'password_hash': 1})
print('User doc:', {k: v[:20] + '...' if k == 'password_hash' else v for k, v in u.items() if k != '_id'})
print(f'\nLogin with: admin@paperiq.local / {new_password}')
