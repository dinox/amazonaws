import boto.ec2, time

ips = ["54.200.217.6", "54.201.11.70"]
lbs = []
conn = boto.ec2.connect_to_region("us-west-2")
for ip in ips:
    reservation = conn.run_instances("ami-4462fa74", key_name='herik#cburkhal', instance_type='t1.micro')
    instance = reservation.instances[0]
    lbs.append(instance)
    print 'Waiting for instance to start...'
    status = instance.update()
    while status == 'pending':
		time.sleep(1)
		status = instance.update()
    if status == 'running':
        conn.associate_address(instance.id, ip)
        print('New loadbalancer "' + instance.id + '" accessible at ' + ip)
    else:
        print('Instance status: ' + status)
raw_input("Press Enter to shutdown loadbalancers...")
conn.terminate_instances(instance_ids=[w.id for w in lbs])
