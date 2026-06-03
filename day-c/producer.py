import csv

def run_producer(q, file_path):
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            q.put(row)
            
    # how do i tell the consumer that i am done and dead?
    q.put(None)