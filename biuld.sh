#Docker for Power Shell
docker build -t dog-weight-tracker:v1.0.0 .
or 
docker build --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') -t dog-weight-tracker:v1.0.0 .
 $imageId = docker images -q  dog-weight-tracker:v1.0.0

docker image ls
docker image inspect $imageId
docker history  $imageId

docker build -t dog-weight-tracker:v1.0.0 .