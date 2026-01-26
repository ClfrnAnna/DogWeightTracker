

#Docker for Power Shell
docker build -t dog-weight-tracker:v1.0.0 .
 $imageId = docker images -q  dog-weight-tracker:v1.0.0

docker image ls
docker image inspect $imageId
docker history  $imageId