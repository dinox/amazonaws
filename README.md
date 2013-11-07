amazonaws
=========

Playing with the Amazon AWS

Make sure your AWS credentials is in your ~/.boto file.

Loadbalancer
Usage: `twistd -noy loadbalancer.py`

startloadbalancer.py:
Usage: `python startloadbalancer.py`
Will start up 2 loadbalancers and two worker units. They are accessible at
elastic IP's 

    54.200.217.6:8080
    54.201.11.70:8080
and runs the factorial server which can calculate factorials. For example

    54.200.217.6:8080/3
will return 6.
