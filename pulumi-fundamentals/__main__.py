"""A Python Pulumi program"""

import pulumi
import os
import pulumi_docker as docker

config = pulumi.Config()
frontend_port = config.require_int("frontend_port")
backend_port = config.require_int("backend_port")
mongo_port = config.require_int("mongo_port")
mongo_host = config.require("mongo_host")
database = config.require("database")
node_environment = config.require("node_environment")

stack = pulumi.get_stack()

backend_image_name = "backend"
backend = docker.Image("backend", 
    build=docker.DockerBuild(
    context=f"{os.getcwd()}/app/backend"),
    image_name=f"{backend_image_name}:{stack}",
    skip_push=True
)

frontend_image_name = "frontend"
frontend = docker.Image("frontend",
    build=docker.DockerBuild(context=f"{os.getcwd()}/app/frontend"),
    image_name=f"{frontend_image_name}:{stack}",
    skip_push=True
)

mongo_image = docker.RemoteImage("mongo", name="mongo:bionic")

network = docker.Network("network", name=f"services-{stack}")

mongo_container = docker.Container("mongo_container",
    image=mongo_image.latest,
    name=f"mongo-{stack}",
    ports=[
        docker.ContainerPortArgs(
            internal=mongo_port,
            external=mongo_port,
        )
    ],
    networks_advanced=[
        docker.ContainerNetworksAdvancedArgs(
            name=network.name,
            aliases=["mongo"],
        )
    ]
)

backend_container = docker.Container("backend_container",
    name=f"backend-{stack}",
    image=backend.base_image_name,
    ports=[docker.ContainerPortArgs(
        internal=backend_port,
        external=backend_port,
    )],
    envs=[
        f"DATABASE_HOST={mongo_host}",
        f"DATABASE_NAME={database}",
        f"NODE_ENV={node_environment}",
    ],
    networks_advanced=[docker.ContainerNetworksAdvancedArgs(
        name=network.name,
    )],
    opts=pulumi.ResourceOptions(depends_on=[mongo_container])
)

data_seed_container = docker.Container("data_seed_container",
                                       image=mongo_image.latest,
                                       name="data_seed",
                                       must_run=False,
                                       rm=True,
                                       opts=pulumi.ResourceOptions(depends_on=[backend_container]),
                                       mounts=[docker.ContainerMountArgs(
                                           target="/home/products.json",
                                           type="bind",
                                           source=f"{os.getcwd()}/products.json"
                                       )],
                                       command=[
                                           "sh", "-c",
                                           "mongoimport --host mongo --db cart --collection products --type json --file /home/products.json --jsonArray"
                                       ],
                                       networks_advanced=[docker.ContainerNetworksAdvancedArgs(
                                           name=network.name
                                       )]
                                       )

frontend_contianer = docker.Container("frontend_container",
    image=frontend.base_image_name,
    name=f"frontend-{stack}",
    ports=[
        docker.ContainerPortArgs(
            internal=frontend_port,
            external=frontend_port,
        )
    ],
    envs=[
        f"LISTEN_PORT={frontend_port}",
        f"HTTP_PROXY=backend-{stack}:{backend_port}",
    ],
    networks_advanced=[docker.ContainerNetworksAdvancedArgs(
        name=network.name,
    )]
)