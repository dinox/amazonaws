import boto.ec2, time
conn = boto.ec2.connect_to_region("us-west-2")
worker = conn.run_instances("ami-64ad3554", key_name='herik#cburkhal', instance_type='t1.micro')
time.sleep(30)
raw_input("Press Enter to shutdown worker...")
conn.terminate_instances(instance_ids=[w.id for w in worker.instances])
