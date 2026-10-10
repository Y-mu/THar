from langHar.api.app import create_app
from langHar.bootstrap import create_container


app = create_app(container_factory=create_container)
