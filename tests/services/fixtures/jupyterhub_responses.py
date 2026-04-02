"""Mock JupyterHub API responses for testing"""

# OAuth token exchange response
JUPYTERHUB_TOKEN_RESPONSE = {
    "access_token": "test-access-token-abc123",
    "token_type": "Bearer",
}

# User info response (regular user)
JUPYTERHUB_USER_RESPONSE = {
    "name": "testuser",
    "admin": False,
    "groups": ["users"],
    "server": "/user/testuser/",
}

# Admin user response
JUPYTERHUB_ADMIN_USER_RESPONSE = {
    "name": "admin",
    "admin": True,
    "groups": ["admin", "users"],
    "server": "/user/admin/",
}

# Second user for multi-user tests
JUPYTERHUB_USER2_RESPONSE = {
    "name": "user2",
    "admin": False,
    "groups": ["users"],
    "server": "/user/user2/",
}
