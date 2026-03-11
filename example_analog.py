"""
Analog Waveform Generator Examples for Accordion.py

This module provides examples for generating various analog waveforms
on MPIO channels using the Accordion hardware wrapper.

Features:
- Multiple waveform types: sine, square, sawtooth, triangle, ramp, chirp, noise
- Threading support for continuous waveform generation
- Live parameter adjustment from Jupyter Lab
- Easy start/stop control
- Batch setting of multiple channels simultaneously

Usage in Jupyter Lab:
    from example_analog import AnalogWaveformGenerator
    
    # Create generator instance
    gen = AnalogWaveformGenerator()
    
    # Start generating waveforms
    gen.start()
    
    # Adjust parameters live
    gen.set_frequency('MPIO0', 100)  # Change sine wave frequency
    gen.set_amplitude('MPIO1', 2.5)  # Change square amplitude
    
    # Stop generating
    gen.stop()
"""

import threading
import time
import math
import random
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
import accordion


# --- Waveform Generators ---

def sine_wave(t: float, frequency: float, amplitude: float, offset: float) -> float:
    """Generate sine wave value: A*sin(2*pi*f*t) + offset"""
    return amplitude * math.sin(2 * math.pi * frequency * t) + offset


def square_wave(t: float, frequency: float, amplitude: float, offset: float) -> float:
    """Generate square wave value"""
    period = 1.0 / frequency if frequency > 0 else 1.0
    phase = (t % period) / period
    value = amplitude if phase < 0.5 else -amplitude
    return value + offset


def sawtooth_wave(t: float, frequency: float, amplitude: float, offset: float) -> float:
    """Generate sawtooth wave value (ramps from -amplitude to +amplitude)"""
    period = 1.0 / frequency if frequency > 0 else 1.0
    phase = (t % period) / period
    value = 2 * amplitude * (phase - 0.5)
    return value + offset


def triangle_wave(t: float, frequency: float, amplitude: float, offset: float) -> float:
    """Generate triangle wave value"""
    period = 1.0 / frequency if frequency > 0 else 1.0
    phase = (t % period) / period
    
    if phase < 0.25:
        value = 4 * amplitude * phase
    elif phase < 0.75:
        value = 2 * amplitude * (0.5 - (phase - 0.25))
    else:
        value = -4 * amplitude * (1 - phase)
    
    return value + offset


def ramp_wave(t: float, frequency: float, amplitude: float, offset: float) -> float:
    """Generate ramp wave (linearly increasing)"""
    period = 1.0 / frequency if frequency > 0 else 1.0
    phase = (t % period) / period
    value = 2 * amplitude * phase - amplitude
    return value + offset


def chirp_wave(t: float, frequency: float, amplitude: float, offset: float, 
               freq_start: float = 1, freq_end: float = 100) -> float:
    """Generate chirp wave (frequency sweep)"""
    # Frequency increases linearly from freq_start to freq_end over period
    period = 1.0 / frequency if frequency > 0 else 1.0
    phase = (t % period) / period
    
    # Calculate instantaneous frequency
    f = freq_start + (freq_end - freq_start) * phase
    
    # Phase accumulation for chirp
    instantaneous_phase = 2 * math.pi * (freq_start * phase + 
                                        (freq_end - freq_start) * phase**2 / 2)
    value = amplitude * math.sin(instantaneous_phase)
    return value + offset


def noise_wave(t: float, frequency: float, amplitude: float, offset: float) -> float:
    """Generate white noise (updates at frequency rate)"""
    # Update noise at frequency rate
    if frequency > 0:
        phase = (t * frequency) % 1.0
        if phase < 0.01:  # Update every period
            noise_wave._cache = random.uniform(-amplitude, amplitude)
        return noise_wave._cache + offset
    return offset

# Initialize cache for noise
noise_wave._cache = 0.0


def pulse_wave(t: float, frequency: float, amplitude: float, offset: float, 
               duty_cycle: float = 0.5) -> float:
    """Generate pulse wave with adjustable duty cycle"""
    period = 1.0 / frequency if frequency > 0 else 1.0
    phase = (t % period) / period
    value = amplitude if phase < duty_cycle else -amplitude
    return value + offset


# --- Waveform Registry ---

WAVEFORMS = {
    'sine': sine_wave,
    'square': square_wave,
    'sawtooth': sawtooth_wave,
    'triangle': triangle_wave,
    'ramp': ramp_wave,
    'chirp': chirp_wave,
    'noise': noise_wave,
    'pulse': pulse_wave,
}


@dataclass
class ChannelConfig:
    """Configuration for a single waveform channel"""
    name: str
    waveform_type: str = 'sine'
    frequency: float = 10.0  # Hz
    amplitude: float = 2.5  # Volts
    offset: float = 2.5  # Volts (center)
    enabled: bool = True
    vmin: float = 0.0  # Voltage minimum
    vmax: float = 5.0  # Voltage maximum
    extra_params: Dict = field(default_factory=dict)  # For pulse duty cycle, chirp range, etc.


class AnalogWaveformGenerator:
    """
    Generate multiple analog waveforms simultaneously on MPIO channels
    
    Features:
    - Support for 8-16 channels (MPIO0-MPIO15)
    - Multiple waveform types
    - Thread-based continuous generation
    - Live parameter adjustment
    - Voltage clamping to safe ranges
    
    Example:
        gen = AnalogWaveformGenerator()
        
        # Configure channels
        gen.add_channel('MPIO0', waveform_type='sine', frequency=10)
        gen.add_channel('MPIO1', waveform_type='square', frequency=5)
        gen.add_channel('MPIO2', waveform_type='sawtooth', frequency=2)
        
        # Start generation
        gen.start()
        time.sleep(10)
        gen.stop()
    """
    
    def __init__(self, update_rate: float = 1000, voltage_range: tuple = (0.0, 5.0)):
        """
        Initialize the waveform generator
        
        Args:
            update_rate: Updates per second (Hz)
            voltage_range: (min_voltage, max_voltage) for clamping
        """
        self.update_rate = update_rate
        self.vmin, self.vmax = voltage_range
        self.update_interval = 1.0 / update_rate
        
        self.channels: Dict[str, ChannelConfig] = {}
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.start_time = 0.0
        self._lock = threading.Lock()
        
    def add_channel(self, 
                   channel_name: str,
                   waveform_type: str = 'sine',
                   frequency: float = 10.0,
                   amplitude: float = 2.5,
                   offset: float = 2.5,
                   **kwargs) -> None:
        """
        Add a waveform channel configuration
        
        Args:
            channel_name: MPIO channel name (e.g., 'MPIO0')
            waveform_type: Type of waveform ('sine', 'square', 'sawtooth', 'triangle', 'ramp', 'chirp', 'noise', 'pulse')
            frequency: Frequency in Hz
            amplitude: Amplitude in Volts
            offset: DC offset in Volts (center of waveform)
            **kwargs: Extra parameters (e.g., duty_cycle for pulse, freq_start/freq_end for chirp)
        """
        if waveform_type not in WAVEFORMS:
            print(f"Warning: Unknown waveform type '{waveform_type}'. Available types: {list(WAVEFORMS.keys())}")
            waveform_type = 'sine'
        
        with self._lock:
            self.channels[channel_name] = ChannelConfig(
                name=channel_name,
                waveform_type=waveform_type,
                frequency=frequency,
                amplitude=amplitude,
                offset=offset,
                vmin=self.vmin,
                vmax=self.vmax,
                extra_params=kwargs
            )
    
    def configure_channels_presets(self, num_channels: int = 8) -> None:
        """
        Configure predefined channel presets (for quick setup)
        
        Args:
            num_channels: Number of channels to configure (8 or 16)
        """
        presets = [
            ('sine', 10.0),
            ('square', 5.0),
            ('sawtooth', 3.0),
            ('triangle', 2.0),
            ('ramp', 8.0),
            ('chirp', 1.0),
            ('pulse', 4.0),
            ('noise', 10.0),
        ]
        
        with self._lock:
            for i in range(min(num_channels, len(presets))):
                waveform_type, frequency = presets[i % len(presets)]
                self.add_channel(
                    f'MPIO{i}',
                    waveform_type=waveform_type,
                    frequency=frequency,
                    amplitude=2.0,
                    offset=2.5
                )
    
    def set_frequency(self, channel_name: str, frequency: float) -> None:
        """Set the frequency of a channel (Hz)"""
        with self._lock:
            if channel_name in self.channels:
                self.channels[channel_name].frequency = max(0.01, frequency)
    
    def set_amplitude(self, channel_name: str, amplitude: float) -> None:
        """Set the amplitude of a channel (Volts)"""
        with self._lock:
            if channel_name in self.channels:
                self.channels[channel_name].amplitude = amplitude
    
    def set_offset(self, channel_name: str, offset: float) -> None:
        """Set the DC offset of a channel (Volts)"""
        with self._lock:
            if channel_name in self.channels:
                self.channels[channel_name].offset = offset
    
    def set_waveform_type(self, channel_name: str, waveform_type: str) -> None:
        """Change the waveform type for a channel"""
        with self._lock:
            if channel_name in self.channels:
                if waveform_type in WAVEFORMS:
                    self.channels[channel_name].waveform_type = waveform_type
                else:
                    print(f"Unknown waveform type: {waveform_type}")
    
    def enable_channel(self, channel_name: str, enabled: bool = True) -> None:
        """Enable or disable a channel"""
        with self._lock:
            if channel_name in self.channels:
                self.channels[channel_name].enabled = enabled
    
    def _clamp_voltage(self, voltage: float) -> float:
        """Clamp voltage to safe operating range"""
        return max(self.vmin, min(self.vmax, voltage))
    
    def _generate_value(self, channel: ChannelConfig, elapsed_time: float) -> float:
        """Generate the next value for a channel"""
        if not channel.enabled:
            return channel.offset
        
        waveform_func = WAVEFORMS.get(channel.waveform_type, sine_wave)
        
        # Call waveform with extra parameters if available
        if channel.waveform_type == 'pulse':
            duty_cycle = channel.extra_params.get('duty_cycle', 0.5)
            value = waveform_func(elapsed_time, channel.frequency, 
                                 channel.amplitude, channel.offset, duty_cycle)
        elif channel.waveform_type == 'chirp':
            freq_start = channel.extra_params.get('freq_start', 1)
            freq_end = channel.extra_params.get('freq_end', 100)
            value = waveform_func(elapsed_time, channel.frequency,
                                 channel.amplitude, channel.offset,
                                 freq_start, freq_end)
        else:
            value = waveform_func(elapsed_time, channel.frequency,
                                 channel.amplitude, channel.offset)
        
        return self._clamp_voltage(value)
    
    def _generator_thread(self) -> None:
        """Main thread function for generating waveforms"""
        print(f"[AnalogWaveformGenerator] Started with {len(self.channels)} channels")
        
        try:
            while self.running:
                with self._lock:
                    elapsed_time = time.time() - self.start_time
                    
                    # Generate values for all channels
                    channel_names = []
                    values = []
                    
                    for channel_name, channel in self.channels.items():
                        value = self._generate_value(channel, elapsed_time)
                        channel_names.append(channel_name)
                        # Format value to 4 decimal places as string
                        values.append(f"{value:.4f}")
                    
                    # Set all values at once
                    if channel_names and values:
                        try:
                            accordion.set_values(channel_names, values)
                        except Exception as e:
                            print(f"[AnalogWaveformGenerator] Error setting values: {e}")
                
                # Sleep for update interval
                time.sleep(self.update_interval)
        
        except Exception as e:
            print(f"[AnalogWaveformGenerator] Thread error: {e}")
        finally:
            print("[AnalogWaveformGenerator] Stopped")
    
    def start(self) -> None:
        """Start generating waveforms"""
        if self.running:
            print("Generator already running")
            return
        
        if not self.channels:
            print("No channels configured. Use add_channel() or configure_channels_presets()")
            return
        
        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._generator_thread, daemon=True)
        self.thread.start()
        print(f"[AnalogWaveformGenerator] Started generating waveforms on {len(self.channels)} channels")
    
    def stop(self) -> None:
        """Stop generating waveforms"""
        if not self.running:
            print("Generator not running")
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print("[AnalogWaveformGenerator] Stopped")
    
    def is_running(self) -> bool:
        """Check if generator is running"""
        return self.running
    
    def get_status(self) -> Dict:
        """Get current status of all channels"""
        with self._lock:
            status = {
                'running': self.running,
                'num_channels': len(self.channels),
                'update_rate': self.update_rate,
                'voltage_range': (self.vmin, self.vmax),
                'channels': {}
            }
            
            for channel_name, channel in self.channels.items():
                status['channels'][channel_name] = {
                    'type': channel.waveform_type,
                    'frequency': channel.frequency,
                    'amplitude': channel.amplitude,
                    'offset': channel.offset,
                    'enabled': channel.enabled,
                    'extra_params': channel.extra_params
                }
            
            return status
    
    def print_status(self) -> None:
        """Print formatted status"""
        status = self.get_status()
        print(f"\n{'='*60}")
        print(f"Analog Waveform Generator Status")
        print(f"{'='*60}")
        print(f"Running: {status['running']}")
        print(f"Total Channels: {status['num_channels']}")
        print(f"Update Rate: {status['update_rate']} Hz")
        print(f"Voltage Range: {status['voltage_range'][0]} - {status['voltage_range'][1]} V")
        print(f"\n{'Channel Name':<12} {'Type':<12} {'Freq (Hz)':<12} {'Amp (V)':<12} {'Offset (V)':<12} {'Enabled':<10}")
        print(f"{'-'*72}")
        
        for channel_name, config in status['channels'].items():
            print(f"{channel_name:<12} {config['type']:<12} {config['frequency']:<12.2f} "
                  f"{config['amplitude']:<12.2f} {config['offset']:<12.2f} {str(config['enabled']):<10}")
        
        print(f"{'='*60}\n")


# --- Quick Setup Examples ---

def example_basic_setup():
    """Simple example: 3 waveforms on MPIO0-2"""
    print("Running basic 3-channel example...")
    
    gen = AnalogWaveformGenerator()
    gen.add_channel('MPIO0', waveform_type='sine', frequency=10, amplitude=2.0, offset=2.5)
    gen.add_channel('MPIO1', waveform_type='square', frequency=5, amplitude=2.0, offset=2.5)
    gen.add_channel('MPIO2', waveform_type='sawtooth', frequency=3, amplitude=2.0, offset=2.5)
    
    gen.print_status()
    gen.start()
    
    try:
        for i in range(5):
            time.sleep(1)
            print(f"Running... {i+1}s")
    finally:
        gen.stop()


def example_all_waveforms():
    """Show all available waveform types"""
    print("Running all waveforms example...")
    
    gen = AnalogWaveformGenerator(update_rate=500)  # 500 Hz for smooth output
    
    # Add all waveform types
    waveforms = list(WAVEFORMS.keys())
    for i, waveform_type in enumerate(waveforms[:8]):  # Limit to 8 channels
        gen.add_channel(
            f'MPIO{i}',
            waveform_type=waveform_type,
            frequency=5 + i,  # Different frequencies
            amplitude=2.0,
            offset=2.5
        )
    
    gen.print_status()
    gen.start()
    
    try:
        for i in range(10):
            time.sleep(1)
            print(f"Running... {i+1}s")
    finally:
        gen.stop()


def example_16_channels():
    """Full 16-channel preset configuration"""
    print("Running 16-channel preset example...")
    
    gen = AnalogWaveformGenerator(update_rate=500)
    gen.configure_channels_presets(num_channels=16)
    
    gen.print_status()
    gen.start()
    
    try:
        for i in range(5):
            time.sleep(1)
            print(f"Running... {i+1}s")
            
            # Demonstrate live parameter adjustment
            if i == 2:
                print("Changing MPIO0 frequency to 20 Hz...")
                gen.set_frequency('MPIO0', 20)
    finally:
        gen.stop()


if __name__ == "__main__":
    # Run basic example when executed directly
    # Uncomment one of the examples below:
    
    # example_basic_setup()
    example_all_waveforms()
    # example_16_channels()
