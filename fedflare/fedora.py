projects = {
    'epel': {
        "7": {"alias": "7Server"},
        "8/Everything": {},
        "8/Modular": {},
        "next/8/Everything": {},
        "playground/8/Everything": {},
        "testing/7": {},
        "testing/8/Everything": {},
        "testing/8/Modular": {},
        "testing/next/8/Everything": {},
    }
}

archs = [
    "aarch64",
    "ppc64",
    "ppc64le",
    "x86_64",
]


# no ppc64 builds from 8 onwards
for project in projects['epel']:
    project_archs = archs.copy()
    project_repos = []
    if '8' in project:
        project_archs.remove('ppc64')
    if not project.startswith('playground/8/'):
        project_repos.append('SRPMS')
    project_repos.append('source/tree')

    for arch in project_archs:
        arch_base_repo = arch
        arch_debug_repo = f"{arch}/debug"
        if project.startswith('playground/8/'):
            arch_base_repo = f"{arch}/os"
            arch_debug_repo = f"{arch}/debug/tree"
        project_repos.append(arch_base_repo)
        project_repos.append(arch_debug_repo)

    projects['epel'][project]['repos'] = project_repos



