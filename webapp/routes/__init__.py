# © 2026 Omar Mokhtar. All rights reserved.
'''The website's routes, one module per area; ``register_all`` adds them in the order the site always did.'''
from importlib import import_module

AREAS = ('theme', 'sign_in', 'admin', 'people_file', 'my_week', 'requests', 'live_stamps', 'break_changes', 'home', 'runs', 'group_posts', 'analytics', 'schedule_versions', 'schedule_delete', 'channel_needs', 'week_breaks', 'week_channels', 'day', 'exports')


def register_all(app, ctx) -> None:
    for area in AREAS:
        import_module(f".{area}", __name__).register(app, ctx)
