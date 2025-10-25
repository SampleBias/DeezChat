"""
Metrics collection module for DeezChat

Handles performance metrics collection and reporting.
"""

import time
import threading
import logging
import json
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import statistics

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types of metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

@dataclass
class MetricValue:
    """Metric value with timestamp"""
    value: Any
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class Histogram:
    """Histogram metric with buckets"""
    name: str
    buckets: List[float]
    counts: List[int] = field(default_factory=list)
    sum_values: float = 0.0
    count: int = 0
    
    def observe(self, value: float):
        """Observe a value"""
        # Find appropriate bucket
        for i, bucket in enumerate(self.buckets):
            if value <= bucket:
                self.counts[i] += 1
                self.sum_values += value
                self.count += 1
                break
        else:
            # Value is larger than all buckets
            self.counts[-1] += 1
            self.sum_values += value
            self.count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get histogram statistics"""
        if self.count == 0:
            return {
                'count': 0,
                'sum': 0.0,
                'mean': 0.0,
                'min': 0.0,
                'max': 0.0
            }
        
        return {
            'count': self.count,
            'sum': self.sum_values,
            'mean': self.sum_values / self.count,
            'min': self._get_percentile(0),
            'max': self._get_percentile(100),
            'p50': self._get_percentile(50),
            'p95': self._get_percentile(95),
            'p99': self._get_percentile(99)
        }
    
    def _get_percentile(self, percentile: float) -> float:
        """Get value at percentile"""
        if self.count == 0:
            return 0.0
        
        target_count = (percentile / 100.0) * self.count
        current_count = 0
        
        for i, count in enumerate(self.counts):
            current_count += count
            if current_count >= target_count:
                # Return upper bound of bucket
                if i < len(self.buckets) - 1:
                    return self.buckets[i]
                else:
                    return float('inf')
        
        return self.buckets[-1]  # Return max bucket

@dataclass
class Timer:
    """Timer metric for measuring duration"""
    name: str
    count: int = 0
    sum_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    
    def observe(self, duration: float):
        """Observe a duration"""
        self.count += 1
        self.sum_duration += duration
        self.min_duration = min(self.min_duration, duration)
        self.max_duration = max(self.max_duration, duration)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get timer statistics"""
        if self.count == 0:
            return {
                'count': 0,
                'sum': 0.0,
                'mean': 0.0,
                'min': 0.0,
                'max': 0.0
            }
        
        return {
            'count': self.count,
            'sum': self.sum_duration,
            'mean': self.sum_duration / self.count,
            'min': self.min_duration,
            'max': self.max_duration
        }

class MetricsCollector:
    """Metrics collection and reporting system"""
    
    def __init__(self):
        self.counters: Dict[str, float] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, Histogram] = {}
        self.timers: Dict[str, Timer] = {}
        self.tags: Dict[str, str] = {}
        
        # Lock for thread safety
        self._lock = threading.Lock()
        
        # Callbacks for metric events
        self.callbacks: List[Callable[[str, MetricType, Any], None]] = []
        
        logger.debug("Metrics collector initialized")
    
    def increment_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None):
        """Increment a counter metric"""
        with self._lock:
            if name not in self.counters:
                self.counters[name] = 0.0
            
            self.counters[name] += value
            
            # Trigger callbacks
            self._trigger_callbacks(name, MetricType.COUNTER, self.counters[name], tags)
    
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Set a gauge metric"""
        with self._lock:
            self.gauges[name] = value
            
            # Trigger callbacks
            self._trigger_callbacks(name, MetricType.GAUGE, value, tags)
    
    def observe_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Observe a histogram value"""
        with self._lock:
            if name not in self.histograms:
                # Create default histogram with common buckets
                self.histograms[name] = Histogram(
                    name=name,
                    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, float('inf')]
                )
            
            self.histograms[name].observe(value)
            
            # Trigger callbacks
            stats = self.histograms[name].get_stats()
            self._trigger_callbacks(name, MetricType.HISTOGRAM, stats, tags)
    
    def observe_timer(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """Observe a timer duration"""
        with self._lock:
            if name not in self.timers:
                self.timers[name] = Timer(name=name)
            
            self.timers[name].observe(duration)
            
            # Trigger callbacks
            stats = self.timers[name].get_stats()
            self._trigger_callbacks(name, MetricType.TIMER, stats, tags)
    
    def time_function(self, name: str):
        """Decorator to time function execution"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    self.observe_timer(name, duration)
            return wrapper
        return decorator
    
    def register_callback(self, callback: Callable[[str, MetricType, Any], None]):
        """Register callback for metric events"""
        self.callbacks.append(callback)
        logger.debug(f"Registered metrics callback: {callback.__name__}")
    
    def unregister_callback(self, callback: Callable[[str, MetricType, Any], None]):
        """Unregister callback for metric events"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            logger.debug(f"Unregistered metrics callback: {callback.__name__}")
    
    def _trigger_callbacks(self, name: str, metric_type: MetricType, value: Any, tags: Optional[Dict[str, str]]):
        """Trigger all callbacks for a metric event"""
        for callback in self.callbacks:
            try:
                callback(name, metric_type, value)
            except Exception as e:
                logger.error(f"Metrics callback error: {e}")
    
    def get_counter(self, name: str) -> float:
        """Get counter value"""
        with self._lock:
            return self.counters.get(name, 0.0)
    
    def get_gauge(self, name: str) -> float:
        """Get gauge value"""
        with self._lock:
            return self.gauges.get(name, 0.0)
    
    def get_histogram_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """Get histogram statistics"""
        with self._lock:
            if name in self.histograms:
                return self.histograms[name].get_stats()
            return None
    
    def get_timer_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """Get timer statistics"""
        with self._lock:
            if name in self.timers:
                return self.timers[name].get_stats()
            return None
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary"""
        with self._lock:
            metrics = {}
            
            # Add counters
            metrics['counters'] = self.counters.copy()
            
            # Add gauges
            metrics['gauges'] = self.gauges.copy()
            
            # Add histograms
            metrics['histograms'] = {}
            for name, histogram in self.histograms.items():
                metrics['histograms'][name] = histogram.get_stats()
            
            # Add timers
            metrics['timers'] = {}
            for name, timer in self.timers.items():
                metrics['timers'][name] = timer.get_stats()
            
            return metrics
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics"""
        with self._lock:
            summary = {
                'timestamp': time.time(),
                'counters_count': len(self.counters),
                'gauges_count': len(self.gauges),
                'histograms_count': len(self.histograms),
                'timers_count': len(self.timers),
                'total_metrics': len(self.counters) + len(self.gauges) + len(self.histograms) + len(self.timers)
            }
            
            # Add counter totals
            if self.counters:
                summary['total_counter_value'] = sum(self.counters.values())
            
            # Add gauge averages
            if self.gauges:
                summary['average_gauge_value'] = statistics.mean(self.gauges.values())
            
            return summary
    
    def reset_metric(self, name: str):
        """Reset a specific metric"""
        with self._lock:
            if name in self.counters:
                del self.counters[name]
            
            if name in self.gauges:
                del self.gauges[name]
            
            if name in self.histograms:
                del self.histograms[name]
            
            if name in self.timers:
                del self.timers[name]
            
            logger.debug(f"Reset metric: {name}")
    
    def reset_all_metrics(self):
        """Reset all metrics"""
        with self._lock:
            self.counters.clear()
            self.gauges.clear()
            self.histograms.clear()
            self.timers.clear()
            
            logger.debug("Reset all metrics")
    
    def export_metrics(self, format: str = "json") -> str:
        """Export metrics to string format"""
        metrics = self.get_all_metrics()
        
        if format.lower() == "json":
            return json.dumps(metrics, indent=2)
        elif format.lower() == "prometheus":
            return self._export_prometheus(metrics)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_prometheus(self, metrics: Dict[str, Any]) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        
        # Export counters
        for name, value in metrics['counters'].items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        
        # Export gauges
        for name, value in metrics['gauges'].items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        
        # Export histograms
        for name, stats in metrics['histograms'].items():
            lines.append(f"# TYPE {name} histogram")
            
            # Add bucket counts
            for i, bucket in enumerate(stats['buckets']):
                lines.append(f"{name}_bucket{{le=\"{bucket}\"}} {stats['counts'][i]}")
            
            # Add stats
            lines.append(f"{name}_sum {stats['sum']}")
            lines.append(f"{name}_count {stats['count']}")
        
        # Export timers
        for name, stats in metrics['timers'].items():
            lines.append(f"# TYPE {name} histogram")
            lines.append(f"{name}_sum {stats['sum']}")
            lines.append(f"{name}_count {stats['count']}")
            lines.append(f"{name}_seconds {stats['sum']}")
        
        return "\n".join(lines)
    
    def set_tag(self, key: str, value: str):
        """Set a global tag"""
        with self._lock:
            self.tags[key] = value
    
    def get_tag(self, key: str) -> Optional[str]:
        """Get a global tag"""
        with self._lock:
            return self.tags.get(key)
    
    def clear_tag(self, key: str):
        """Clear a global tag"""
        with self._lock:
            if key in self.tags:
                del self.tags[key]
    
    def get_all_tags(self) -> Dict[str, str]:
        """Get all global tags"""
        with self._lock:
            return self.tags.copy()
    
    def print_metrics_summary(self):
        """Print a summary of all metrics"""
        summary = self.get_metrics_summary()
        
        print("\n=== Metrics Summary ===")
        print(f"Total Metrics: {summary['total_metrics']}")
        print(f"Counters: {summary['counters_count']}")
        print(f"Gauges: {summary['gauges_count']}")
        print(f"Histograms: {summary['histograms_count']}")
        print(f"Timers: {summary['timers_count']}")
        
        if 'total_counter_value' in summary:
            print(f"Total Counter Value: {summary['total_counter_value']}")
        
        if 'average_gauge_value' in summary:
            print(f"Average Gauge Value: {summary['average_gauge_value']:.2f}")
        
        print("========================")
    
    def log_metrics_summary(self):
        """Log metrics summary"""
        summary = self.get_metrics_summary()
        
        logger.info(f"Metrics summary: {summary['total_metrics']} total metrics")
        logger.info(f"Counters: {summary['counters_count']}, total value: {summary.get('total_counter_value', 0)}")
        logger.info(f"Gauges: {summary['gauges_count']}, average: {summary.get('average_gauge_value', 0):.2f}")
        logger.info(f"Histograms: {summary['histograms_count']}")
        logger.info(f"Timers: {summary['timers_count']}")

# Convenience functions for common metrics
def create_performance_metrics() -> MetricsCollector:
    """Create a metrics collector with common performance metrics"""
    collector = MetricsCollector()
    
    # Common performance histograms
    collector.histograms['message_latency'] = Histogram(
        name='message_latency',
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf')]
    )
    
    collector.histograms['message_size'] = Histogram(
        name='message_size',
        buckets=[10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000, float('inf')]
    )
    
    collector.histograms['file_size'] = Histogram(
        name='file_size',
        buckets=[1024, 4096, 16384, 65536, 262144, 1048576, 4194304, 16777216, 67108864, float('inf')]
    )
    
    collector.timers['message_processing'] = Timer(name='message_processing')
    collector.timers['encryption_operation'] = Timer(name='encryption_operation')
    collector.timers['database_operation'] = Timer(name='database_operation')
    collector.timers['network_operation'] = Timer(name='network_operation')
    
    # Common counters
    collector.counters['messages_sent'] = 0.0
    collector.counters['messages_received'] = 0.0
    collector.counters['messages_failed'] = 0.0
    collector.counters['files_sent'] = 0.0
    collector.counters['files_received'] = 0.0
    collector.counters['connections_established'] = 0.0
    collector.counters['connections_failed'] = 0.0
    collector.counters['handshakes_completed'] = 0.0
    collector.counters['handshakes_failed'] = 0.0
    
    # Common gauges
    collector.gauges['active_connections'] = 0.0
    collector.gauges['active_peers'] = 0.0
    collector.gauges['queue_size'] = 0.0
    collector.gauges['memory_usage'] = 0.0
    collector.gauges['cpu_usage'] = 0.0
    
    return collector

# Decorator for timing functions
def time_metric(collector: MetricsCollector, metric_name: str):
    """Decorator to time function execution with metrics"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                collector.observe_timer(metric_name, duration)
        return wrapper
    return decorator

# Context manager for timing operations
class TimedOperation:
    """Context manager for timing operations"""
    
    def __init__(self, collector: MetricsCollector, metric_name: str):
        self.collector = collector
        self.metric_name = metric_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.collector.observe_timer(self.metric_name, duration)