def normalize_delegation(delegation_role: str):
    prefix = "targets/"
    if not delegation_role.startswith(prefix):
        delegation_role = prefix + delegation_role
    return delegation_role
