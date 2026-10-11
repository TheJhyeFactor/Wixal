"""Import skill text and bounded supporting files as immutable workspace snapshots."""
import hashlib
from pathlib import Path, PurePosixPath
from .memory import owner
from .storage import identity, now

SUPPORT_DIRS = ('references', 'templates', 'assets', 'scripts', 'examples')


def visible(store):
    return [s for s in store.data['skills'] if s.get('owner', 'guest') == owner(store)]


def import_skill(store, source):
    from .tools import sensitive
    path = Path(source).expanduser()
    if path.is_symlink():
        raise ValueError('Skill sources cannot be symbolic links')
    path = path.resolve(strict=True)
    if sensitive(path) or not path.is_file() or path.suffix.lower() != '.md' or path.stat().st_size > 24000:
        raise ValueError('Select a Markdown skill below 24 KB outside credential paths')
    content = path.read_text()
    if not content.strip():
        raise ValueError('Skill instructions cannot be empty')
    resources = {}
    total = 0
    if path.name == 'SKILL.md':
        for folder in SUPPORT_DIRS:
            root = path.parent / folder
            if root.is_symlink():
                raise ValueError('Skill supporting directories cannot be symbolic links')
            if not root.is_dir():
                continue
            for file in sorted(root.rglob('*')):
                relative = file.relative_to(path.parent).as_posix()
                if file.is_symlink():
                    raise ValueError('Skill supporting files cannot be symbolic links')
                if not file.is_file() or sensitive(relative):
                    continue
                if file.stat().st_size > 24000:
                    raise ValueError('Each skill supporting file must be below 24 KB')
                try:
                    text = file.read_text()
                except UnicodeError:
                    continue  # Binary assets are not model-readable instructions.
                if '\0' in text:
                    continue
                total += len(text.encode())
                if total > 192000 or len(resources) >= 32:
                    raise ValueError('Skill supporting files exceed 32 files or 192 KB')
                resources[relative] = text
    return dict(id=identity(), owner=owner(store), name=path.parent.name if path.name == 'SKILL.md' else path.stem,
                description=next(line for line in content.splitlines() if line.strip())[:200],
                content=content, resources=resources, source=str(path), created=now())


def load(store, args):
    skill = next((s for s in visible(store) if s['name'] == args['name']), None)
    if skill is None:
        raise ValueError('Unknown skill in this workspace identity')
    resource = args.get('resource')
    if resource:
        path = PurePosixPath(resource)
        if path.is_absolute() or '..' in path.parts or resource not in skill.get('resources', {}):
            raise ValueError('Choose an imported supporting file from this skill')
        content = skill['resources'][resource]
    else:
        content = skill['content']
    offset, maximum = args.get('offset', 0), args.get('max_chars', 12000)
    if offset > len(content):
        raise ValueError('Offset exceeds skill text length')
    return dict(name=skill['name'], resource=resource, instructions=content[offset:offset + maximum],
                offset=offset, next_offset=min(len(content), offset + maximum), more=offset + maximum < len(content),
                total_chars=len(content), sha256=hashlib.sha256(content.encode()).hexdigest(),
                resources=[dict(path=k, characters=len(v)) for k, v in skill.get('resources', {}).items()],
                note='Imported snapshot. Read supporting files only when relevant; scripts are text and never execute on load.')
