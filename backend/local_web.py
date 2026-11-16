"""Loopback built frontend/API composition; application startup stays in main."""
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles


def build_directory(directory):
    directory = Path(directory).absolute()
    index = directory/'index.html'
    if (directory.resolve() != directory or not directory.is_dir()
            or index.is_symlink() or not index.is_file()):
        raise ValueError('Regular frontend build required: run npm run build')
    return directory


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        if path not in ('', '.') and any(part.startswith('.') for part in PurePosixPath(path).parts):
            raise HTTPException(404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            # Missing assets/API/media must not silently turn into index.html.
            accept = dict(scope.get('headers', [])).get(b'accept', b'').lower()
            if (error.status_code != 404 or scope['method'] not in ('GET', 'HEAD')
                    or b'text/html' not in accept or PurePosixPath(path).suffix):
                raise
            return await super().get_response('index.html', scope)


def build_app(api, directory, images):
    directory = build_directory(directory)
    @asynccontextmanager
    async def lifespan(_wrapper):
        async with api.router.lifespan_context(api):
            yield
    return Starlette(routes=[Mount('/api', app=api),
                             Mount('/card-images', app=StaticFiles(directory=images)),
                             Mount('/', app=FrontendFiles(directory=directory, html=True))],
                     lifespan=lifespan)


def create_app():
    directory = build_directory(Path(__file__).resolve().parents[1]/'frontend/dist')
    import main  # Only after validating the build; existing ownership/startup unchanged.
    return build_app(main.app, directory, main.CACHE_DIR)
