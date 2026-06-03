import queue
import threading
from producer import run_producer
from consumer import run_consumer

def main():
    csv_file = 'machine_temperature_system_failure.csv'
    output_file = 'features.parquet'
    
    # thread-safe queue for in-memory message transport
    q = queue.Queue()
    
    # define threads
    producer_thread = threading.Thread(target=run_producer, args=(q, csv_file))
    consumer_thread = threading.Thread(target=run_consumer, args=(q, output_file))
    
    # start execution
    producer_thread.start()
    consumer_thread.start()
    
    # start, then die, then these forks join the parent thread
    producer_thread.join()
    consumer_thread.join()

if __name__ == '__main__':
    main()