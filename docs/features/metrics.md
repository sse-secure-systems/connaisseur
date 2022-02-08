# Metrics

Connaisseur exposes metrics about usage of the `/mutate` endpoint and general information about the python process using [Prometheus Flask Exporter](https://pypi.org/project/prometheus-flask-exporter/) through the `/metrics` endpoint.

This for example allows visualizing the number of allowed or denied resource requests.

## Example

```
# HELP python_gc_objects_collected_total Objects collected during gc
# TYPE python_gc_objects_collected_total counter
python_gc_objects_collected_total{generation="0"} 4422.0
python_gc_objects_collected_total{generation="1"} 1866.0
python_gc_objects_collected_total{generation="2"} 0.0
# HELP python_gc_objects_uncollectable_total Uncollectable object found during GC
# TYPE python_gc_objects_uncollectable_total counter
python_gc_objects_uncollectable_total{generation="0"} 0.0
python_gc_objects_uncollectable_total{generation="1"} 0.0
python_gc_objects_uncollectable_total{generation="2"} 0.0
# HELP python_gc_collections_total Number of times this generation was collected
# TYPE python_gc_collections_total counter
python_gc_collections_total{generation="0"} 163.0
python_gc_collections_total{generation="1"} 14.0
python_gc_collections_total{generation="2"} 1.0
# HELP python_info Python platform information
# TYPE python_info gauge
python_info{implementation="CPython",major="3",minor="10",patchlevel="2",version="3.10.2"} 1.0
# HELP process_virtual_memory_bytes Virtual memory size in bytes.
# TYPE process_virtual_memory_bytes gauge
process_virtual_memory_bytes 6.1161472e+07
# HELP process_resident_memory_bytes Resident memory size in bytes.
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes 4.595712e+07
# HELP process_start_time_seconds Start time of the process since unix epoch in seconds.
# TYPE process_start_time_seconds gauge
process_start_time_seconds 1.6436681112e+09
# HELP process_cpu_seconds_total Total user and system CPU time spent in seconds.
# TYPE process_cpu_seconds_total counter
process_cpu_seconds_total 3.3
# HELP process_open_fds Number of open file descriptors.
# TYPE process_open_fds gauge
process_open_fds 12.0
# HELP process_max_fds Maximum number of open file descriptors.
# TYPE process_max_fds gauge
process_max_fds 1.048576e+06
# HELP exporter_info Information about the Prometheus Flask exporter
# TYPE exporter_info gauge
exporter_info{version="0.18.7"} 1.0
# HELP http_request_duration_seconds Flask HTTP request duration in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.1",method="POST",path="/mutate",status="200"} 5.0
http_request_duration_seconds_bucket{le="0.25",method="POST",path="/mutate",status="200"} 5.0
http_request_duration_seconds_bucket{le="0.5",method="POST",path="/mutate",status="200"} 5.0
http_request_duration_seconds_bucket{le="0.75",method="POST",path="/mutate",status="200"} 8.0
http_request_duration_seconds_bucket{le="1.0",method="POST",path="/mutate",status="200"} 8.0
http_request_duration_seconds_bucket{le="2.5",method="POST",path="/mutate",status="200"} 9.0
http_request_duration_seconds_bucket{le="+Inf",method="POST",path="/mutate",status="200"} 9.0
http_request_duration_seconds_count{method="POST",path="/mutate",status="200"} 9.0
http_request_duration_seconds_sum{method="POST",path="/mutate",status="200"} 3.6445974350208417
# HELP http_request_duration_seconds_created Flask HTTP request duration in seconds
# TYPE http_request_duration_seconds_created gauge
http_request_duration_seconds_created{method="POST",path="/mutate",status="200"} 1.643668194758098e+09
# HELP http_request_total Total number of HTTP requests
# TYPE http_request_total counter
http_request_total{method="POST",status="200"} 9.0
# HELP http_request_created Total number of HTTP requests
# TYPE http_request_created gauge
http_request_created{method="POST",status="200"} 1.6436681947581613e+09
# HELP http_request_exceptions_total Total number of HTTP requests which resulted in an exception
# TYPE http_request_exceptions_total counter
# HELP mutate_requests_total Total number of mutate requests
# TYPE mutate_requests_total counter
mutate_requests_total{allowed="False",status_code="403"} 4.0
mutate_requests_total{allowed="True",status_code="202"} 5.0
# HELP mutate_requests_created Total number of mutate requests
# TYPE mutate_requests_created gauge
mutate_requests_created{allowed="False",status_code="403"} 1.643760946491879e+09
mutate_requests_created{allowed="True",status_code="202"} 1.6437609592007663e+09
```

