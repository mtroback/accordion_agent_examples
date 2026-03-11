# -*- coding: utf-8 -*-
import threading
import time
import colorsys
from typing import List, Callable, Optional, Dict, Tuple
import numpy as np

import accordion as acc


# ============================================================================
# LED POSITION MAP - STATIC CONFIGURATION
# ============================================================================
# Physical layout: 2x2 modules, each module has 3 rows x 2 columns of LEDs
# Total: 6 rows x 4 columns = 24 LEDs
#
# Maps (row, col) -> LED channel name

LED_POSITION_MAP: Dict[Tuple[int, int], str] = {
    # Module N1 (top-left) - Device 0.11
    (0, 0): "0.11.ESH10000355.F1",
    (0, 1): "0.11.ESH10000355.C1",
    (1, 0): "0.11.ESH10000355.E1",
    (1, 1): "0.11.ESH10000355.B1",
    (2, 0): "0.11.ESH10000355.D1",
    (2, 1): "0.11.ESH10000355.A1",
    # Module N3 (top-right) - Device 0.13
    (0, 2): "0.13.ESH10000355.F3",
    (0, 3): "0.13.ESH10000355.C3",
    (1, 2): "0.13.ESH10000355.E3",
    (1, 3): "0.13.ESH10000355.B3",
    (2, 2): "0.13.ESH10000355.D3",
    (2, 3): "0.13.ESH10000355.A3",
    # Module N2 (bottom-left) - Device 0.12
    (3, 0): "0.12.ESH10000355.F2",
    (3, 1): "0.12.ESH10000355.C2",
    (4, 0): "0.12.ESH10000355.E2",
    (4, 1): "0.12.ESH10000355.B2",
    (5, 0): "0.12.ESH10000355.D2",
    (5, 1): "0.12.ESH10000355.A2",
    # Module N4 (bottom-right) - Device 0.14
    (3, 2): "0.14.ESH10000355.F4",
    (3, 3): "0.14.ESH10000355.C4",
    (4, 2): "0.14.ESH10000355.E4",
    (4, 3): "0.14.ESH10000355.B4",
    (5, 2): "0.14.ESH10000355.D4",
    (5, 3): "0.14.ESH10000355.A4",
}


class LEDMapping:
    """Maps physical LED positions to linear channel indices using static configuration."""
    
    # Static configuration
    TOTAL_ROWS = 6
    TOTAL_COLS = 4
    TOTAL_LEDS = 24
    NUM_MODULES_ROWS = 2
    NUM_MODULES_COLS = 2
    LEDS_PER_MODULE_ROWS = 3
    LEDS_PER_MODULE_COLS = 2
    
    def __init__(self, led_channels: List[str]):
        """
        Initialize LED mapping using static position map.
        
        Args:
            led_channels: List of LED channel names in linear order
        """
        self.led_channels = led_channels
        self.total_rows = self.TOTAL_ROWS
        self.total_cols = self.TOTAL_COLS
        self.total_leds = self.TOTAL_LEDS
        self.num_modules_rows = self.NUM_MODULES_ROWS
        self.num_modules_cols = self.NUM_MODULES_COLS
        self.leds_per_module_rows = self.LEDS_PER_MODULE_ROWS
        self.leds_per_module_cols = self.LEDS_PER_MODULE_COLS
        
        # Build position_to_index mapping by matching LED names from static map
        self._position_to_index = {}
        self._position_to_name = {}
        
        print("Initializing LED mapping from static configuration...")
        for (row, col), led_name in LED_POSITION_MAP.items():
            self._position_to_name[(row, col)] = led_name
            
            # Find matching channel by name
            channel_index = None
            for idx, channel in enumerate(self.led_channels):
                if led_name in channel or channel.endswith(led_name):
                    channel_index = idx
                    break
            
            if channel_index is not None:
                self._position_to_index[(row, col)] = channel_index
            else:
                raise ValueError(
                    f"Could not find LED '{led_name}' in available channels.\n"
                    f"Available channels: {self.led_channels}"
                )
        
        print(f"✓ Mapping initialized: {self.total_rows} rows x {self.total_cols} columns = {self.total_leds} LEDs")
    
    def get_led_name(self, row: int, col: int) -> str:
        """Get the LED name/identifier for a position (if using manual mapping)."""
        if (row, col) in self._position_to_name:
            return self._position_to_name[(row, col)]
        return f"LED({row},{col})"
    
    def get_channel_index(self, row: int, col: int) -> int:
        """Get channel index for physical position (row, col)."""
        if (row, col) not in self._position_to_index:
            raise ValueError(f"Invalid LED position ({row}, {col}). Valid range: rows 0-{self.total_rows-1}, cols 0-{self.total_cols-1}")
        return self._position_to_index[(row, col)]
    
    def get_channel(self, row: int, col: int) -> str:
        """Get channel name for physical position (row, col)."""
        idx = self.get_channel_index(row, col)
        if idx >= len(self.led_channels):
            raise ValueError(f"Channel index {idx} out of range for available channels")
        return self.led_channels[idx]
    
    def position_to_index(self, row: int, col: int) -> int:
        """Convert physical (row, col) to linear channel index."""
        return self.get_channel_index(row, col)
    
    def index_to_position(self, index: int) -> Tuple[int, int]:
        """Convert linear channel index to physical (row, col)."""
        for (row, col), idx in self._position_to_index.items():
            if idx == index:
                return row, col
        raise ValueError(f"Index {index} not found in mapping")
    
    def print_mapping_info(self) -> None:
        """Print mapping information for debugging."""
        print("\n" + "=" * 70)
        print("LED MAPPING CONFIGURATION")
        print("=" * 70)
        
        print("Type: Static Position Mapping (from LED_POSITION_MAP)")
        print(f"  Modules: {self.num_modules_rows}x{self.num_modules_cols}")
        print(f"  LEDs per module: {self.leds_per_module_rows}x{self.leds_per_module_cols}")
        
        print(f"\nPhysical Layout:")
        print(f"  Total: {self.total_rows} rows x {self.total_cols} columns = {self.total_leds} LEDs")
        print(f"  Available channels: {len(self.led_channels)}")
        
        # Print grid with LED names and indices
        print(f"\nLED Position Map:")
        print("-" * 70)
        
        header = "      |"
        for col in range(self.total_cols):
            header += f" Col{col:1d} |"
        print(header)
        print("-" * 70)
        
        for row in range(self.total_rows):
            row_str = f"Row{row:1d}  |"
            for col in range(self.total_cols):
                try:
                    idx = self._position_to_index[(row, col)]
                    led_name = self.get_led_name(row, col)
                    # Truncate long names for display
                    display_name = led_name[:4] if len(led_name) > 4 else led_name
                    row_str += f"{idx:3d}  |"
                except:
                    row_str += " -   |"
            print(row_str)
        
        print("-" * 70)
        
        print("\nLED Position Map (row, col -> channel index -> device.address.LED_name):")
        for (row, col), name in sorted(self._position_to_name.items()):
            idx = self._position_to_index.get((row, col), -1)
            print(f"  ({row},{col}) -> [{idx:2d}] {name}")
        
        print("=" * 70 + "\n")


class LEDArray2D:
    """Manager for 2D LED arrays with threading support and efficient batch updates using numpy."""
    
    def __init__(self, led_channels: List[str], mapping: Optional[LEDMapping] = None):
        """
        Initialize LED array manager with numpy-based color storage.
        
        Args:
            led_channels: List of LED channel names (in order as connected)
            mapping: LEDMapping object for physical position to channel mapping.
        """
        if len(led_channels) <= 1:
            raise ValueError("led_channels must contain more than 1 element")
        
        self.led_channels = led_channels
        self.mapping = mapping or LEDMapping(led_channels)
        self.rows = self.mapping.total_rows
        self.cols = self.mapping.total_cols
        self.total_leds = self.mapping.total_leds
        
        # Initialize HSV color array (H, S, V in range 0-1)
        self.hsv_array = np.zeros((self.rows, self.cols, 3), dtype=np.float32)
        # Start with all black (V=0)
        self.hsv_array[:, :, 2] = 0.0
        
        self._stop_event = threading.Event()
        self._thread = None
        
        # Initialize luminance channels to 1.0 for detected modules
        # Extract module IDs from LED channels (e.g., "0.11" from "0.11.ESH10000355.F1")
        module_ids = set()
        for channel in led_channels:
            parts = channel.split(".")
            if len(parts) >= 2:
                module_ids.add(parts[0] + "." + parts[1])
        
        # Build luminance channels for detected modules and set to 1.0
        luminance_channels = [f"{module_id}.ESH10000355.LUMINANCE" for module_id in sorted(module_ids)]
        if luminance_channels:
            acc.set_values(luminance_channels, ["1.0"] * len(luminance_channels))
    
    def _array_to_colors(self) -> tuple[List[str], List[str]]:
        """
        Convert HSV numpy array to channel names and hex color strings.
        
        Returns:
            Tuple of (channel_names_list, color_hex_strings_list)
        """
        channels = []
        colors = []
        
        for row in range(self.rows):
            for col in range(self.cols):
                if (row, col) in self.mapping._position_to_index:
                    channel = self.mapping.get_channel(row, col)
                    h, s, v = self.hsv_array[row, col]
                    
                    # Convert HSV to RGB
                    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
                    r_int = int(max(0, min(255, r * 255)))
                    g_int = int(max(0, min(255, g * 255)))
                    b_int = int(max(0, min(255, b * 255)))
                    color_hex = f"#{r_int:02x}{g_int:02x}{b_int:02x}"
                    
                    channels.append(channel)
                    colors.append(color_hex)
        
        return channels, colors
    
    def update_leds(self) -> None:
        """Batch update all LEDs at once using set_values."""
        channels, colors = self._array_to_colors()
        if channels:
            acc.set_values(channels, colors)
    
    def set_led(self, row: int, col: int, h: float, s: float = 1.0, v: float = 1.0) -> None:
        """
        Set HSV color of LED at given physical row, col position.
        
        Args:
            row: Row index
            col: Column index
            h: Hue (0-1)
            s: Saturation (0-1)
            v: Value/Brightness (0-1)
        """
        if row < 0 or row >= self.rows or col < 0 or col >= self.cols:
            raise ValueError(f"LED position ({row}, {col}) out of bounds")
        self.hsv_array[row, col] = [h % 1.0, s, v]
    
    def set_module_led(self, mod_row: int, mod_col: int, led_row: int, led_col: int, 
                       h: float, s: float = 1.0, v: float = 1.0) -> None:
        """Set HSV color of LED at given module and position within module."""
        phys_row = mod_row * self.mapping.leds_per_module_rows + led_row
        phys_col = mod_col * self.mapping.leds_per_module_cols + led_col
        self.set_led(phys_row, phys_col, h, s, v)
    
    def set_led_by_index(self, index: int, h: float, s: float = 1.0, v: float = 1.0) -> None:
        """Set HSV color of LED by linear channel index."""
        if index < 0 or index >= self.total_leds:
            raise ValueError(f"LED index {index} out of bounds")
        row = index // self.cols
        col = index % self.cols
        self.set_led(row, col, h, s, v)
    
    def set_all(self, h: float, s: float = 1.0, v: float = 1.0) -> None:
        """Set all LEDs to the same HSV color."""
        self.hsv_array[:, :, 0] = h % 1.0
        self.hsv_array[:, :, 1] = s
        self.hsv_array[:, :, 2] = v
    
    def clear(self) -> None:
        """Turn off all LEDs (set V to 0)."""
        self.hsv_array[:, :, 2] = 0.0
        self.update_leds()
    
    @staticmethod
    def rgb_to_hex(r: float, g: float, b: float) -> str:
        """Convert RGB (0-1 range) to hex color string."""
        r_int = int(max(0, min(255, r * 255)))
        g_int = int(max(0, min(255, g * 255)))
        b_int = int(max(0, min(255, b * 255)))
        return f"#{r_int:02x}{g_int:02x}{b_int:02x}"
    def _run_effect(self, effect_func: Callable[[int, float], None], update_interval: float = 0.05) -> None:
        """
        Internal method to run an effect in a thread.
        
        Args:
            effect_func: Function that takes frame number and actual update interval, returns None
            update_interval: Time between frames in seconds (enforced minimum: 0.2s/200ms)
        """
        # Enforce minimum refresh rate of 200ms to accommodate hardware latency
        update_interval = max(update_interval, 0.2)
        
        frame = 0
        self._stop_event.clear()
        missed_frames = 0
        try:
            while not self._stop_event.is_set():
                # Measure time for entire loop iteration
                loop_start = time.time()
                
                # Calculate and apply effects (pass actual update_interval so effects know the refresh rate)
                effect_func(frame, update_interval)
                
                # Measure hardware call time separately
                call_start = time.time()
                self.update_leds()  # Batch update all LEDs
                call_duration = time.time() - call_start
                
                # Calculate total loop duration
                loop_duration = time.time() - loop_start
                
                # Sleep for remaining time to maintain consistent interval
                remaining_time = update_interval - loop_duration
                if remaining_time > 0:
                    time.sleep(remaining_time)
                else:
                    # Log missed timing
                    missed_frames += 1
                    if missed_frames < 10:  # Only log first 10 misses to avoid spam
                        miss_ms = (-remaining_time) * 1000
                        print(f"[Frame {frame}] Timing missed by {miss_ms:.1f}ms (set_values took {call_duration*1000:.1f}ms)")
                
                frame += 1
        finally:
            if missed_frames > 0:
                print(f"[Animation] Total frames that missed timing target: {missed_frames}")
            self.clear()
    
    def start_effect(self, effect_func: Callable[[int, float], None], update_interval: float = 0.2) -> threading.Thread:
        """
        Start an LED effect in a background thread.
        
        Args:
            effect_func: Function that takes frame number and actual update interval, returns None
            update_interval: Time between frames in seconds (minimum: 0.2s/200ms)
            
        Returns:
            The running thread object
        """
        if self._thread is not None and self._thread.is_alive():
            self.stop_effect()
            self._thread.join(timeout=1)
        
        self._thread = threading.Thread(
            target=self._run_effect,
            args=(effect_func, update_interval),
            daemon=True
        )
        self._thread.start()
        return self._thread
    
    def stop_effect(self) -> None:
        """Stop the currently running effect."""
        self._stop_event.set()
    
    def is_running(self) -> bool:
        """Check if an effect is currently running."""
        return self._thread is not None and self._thread.is_alive()
    
    # --- Built-in Effects ---
    
    def rainbow_wave(self, speed: float = 1.0, update_interval: float = 0.2) -> threading.Thread:
        """
        Start a rainbow wave effect across the LED array.
        
        Args:
            speed: Animation speed multiplier
            update_interval: Time between frames in seconds (minimum: 0.2s/200ms)
        """
        def effect(frame, actual_interval):
            for row in range(self.rows):
                for col in range(self.cols):
                    # Calculate hue based on position and frame
                    linear_pos = row * self.cols + col
                    hue = ((linear_pos + frame * speed) % self.total_leds) / self.total_leds
                    self.set_led(row, col, hue, s=1.0, v=1.0)
        
        return self.start_effect(effect, update_interval)
    
    def rainbow_rows(self, speed: float = 1.0, update_interval: float = 0.2) -> threading.Thread:
        """
        Rainbow effect where each row has a different hue (shifts over time).
        
        Args:
            speed: Animation speed multiplier
            update_interval: Time between frames in seconds (minimum: 0.2s/200ms)
        """
        def effect(frame, actual_interval):
            for row in range(self.rows):
                hue = (row / self.rows + frame * speed * 0.02) % 1.0
                for col in range(self.cols):
                    self.set_led(row, col, hue, s=1.0, v=1.0)
        
        return self.start_effect(effect, update_interval)
    
    def rainbow_by_module(self, speed: float = 1.0, update_interval: float = 0.2) -> threading.Thread:
        """
        Rainbow effect where each module has its own distinct color.
        
        Args:
            speed: Animation speed multiplier (hue shift speed)
            update_interval: Time between frames in seconds (minimum: 0.2s/200ms)
        """
        def effect(frame, actual_interval):
            num_modules = self.mapping.num_modules_rows * self.mapping.num_modules_cols
            for mod_row in range(self.mapping.num_modules_rows):
                for mod_col in range(self.mapping.num_modules_cols):
                    # Each module gets a different hue based on its position
                    module_index = mod_row * self.mapping.num_modules_cols + mod_col
                    hue = ((module_index + frame * speed * 0.1) % num_modules) / num_modules
                    
                    # Fill entire module with this color
                    for led_row in range(self.mapping.leds_per_module_rows):
                        for led_col in range(self.mapping.leds_per_module_cols):
                            self.set_module_led(mod_row, mod_col, led_row, led_col, hue, s=1.0, v=1.0)
        
        return self.start_effect(effect, update_interval)
    
    def color_fade(self, duration: float = 2.0, hues: Optional[List[float]] = None, 
                   update_interval: float = 0.2) -> threading.Thread:
        """
        Fade between a set of hues.
        
        Args:
            duration: Time to fade through all hues in seconds
            hues: List of hue values (0-1) to fade between
            update_interval: Time between frames in seconds (minimum: 0.2s/200ms)
        """
        if hues is None:
            hues = [0.0, 0.33, 0.66, 0.0]  # Red, Green, Blue, Red
        
        def effect(frame, actual_interval):
            # Calculate which hue we're at using actual refresh rate
            frames_per_cycle = int(duration / actual_interval)
            progress = (frame % frames_per_cycle) / frames_per_cycle
            hue_index = int(progress * len(hues)) % len(hues)
            hue = hues[hue_index]
            self.set_all(hue, s=1.0, v=1.0)
        
        return self.start_effect(effect, update_interval)
    
    def pulse(self, base_hue: float = 0.0, speed: float = 1.0, 
              update_interval: float = 0.2) -> threading.Thread:
        """
        Pulse all LEDs with brightness variation.
        
        Args:
            base_hue: Hue value (0-1) for the pulse color
            speed: Animation speed multiplier
            update_interval: Time between frames in seconds (minimum: 0.2s/200ms)
        """
        def effect(frame, actual_interval):
            import math
            # Sinusoidal brightness variation, accounting for actual refresh rate
            # Scale frequency up when interval is longer (fewer updates per second)
            brightness = 0.5 + 0.5 * math.sin(frame * speed * 0.1 * (actual_interval / 0.05))
            self.set_all(base_hue, s=1.0, v=brightness)
        
        return self.start_effect(effect, update_interval)
    
    def chase(self, speed: float = 1.0, update_interval: float = 0.2) -> threading.Thread:
        """
        Chase effect - light moves across the array.
        
        Args:
            speed: Animation speed multiplier
            update_interval: Time between frames in seconds (minimum: 0.2s/200ms)
        """
        def effect(frame, actual_interval):
            # Clear array only (not hardware) to reduce visible off-time
            self.hsv_array[:, :, 2] = 0.0
            # Position of the chasing light, accounting for actual refresh rate
            # Scale position advancement up when interval is longer (fewer updates per second)
            pos = int((frame * speed * (actual_interval / 0.05)) % self.total_leds)
            
            # Illuminate LEDs around the chase position
            for i in range(-2, 3):
                idx = (pos + i) % self.total_leds
                row = idx // self.cols
                col = idx % self.cols
                hue = (i + 2) / 5.0  # Gradient of colors
                self.set_led(row, col, hue, s=1.0, v=1.0)
        
        return self.start_effect(effect, update_interval)


if __name__ == "__main__":
    # Configuration
    DEMO_EFFECT_DURATION = 10  # seconds per effect demonstration
    
    print("initializing..")
    acc.attach("py", "agentdemo.local")
    id = acc.get_identification()
    print(f"id: {id}")
    
    LED_connectors = []
    channels = list(acc.get_channel_names())
    for channel in sorted(channels):
        print(channel)
        if "ESH10000355" in channel and not channel.endswith("LUMINANCE"):
            LED_connectors.append(channel)
    
    if len(LED_connectors) > 0:
        print(f"\nFound {len(LED_connectors)} LED channels")
        print("\nNote: Edit LED_POSITION_MAP at the top of the file to customize the physical LED mapping.")
        
        if len(LED_connectors) >= 24:
            # Create LED array with static position mapping
            mapping = LEDMapping(LED_connectors)
            mapping.print_mapping_info()
            
            led_array = LEDArray2D(LED_connectors, mapping)
            
            print("\nDemonstrating effects...")
            
            print(f"\n1. Rainbow wave effect ({DEMO_EFFECT_DURATION} seconds)...")
            led_array.rainbow_wave(speed=2.0)
            time.sleep(DEMO_EFFECT_DURATION)
            led_array.stop_effect()
            
            print(f"2. Rainbow by module effect ({DEMO_EFFECT_DURATION} seconds)...")
            led_array.rainbow_by_module(speed=1.0)
            time.sleep(DEMO_EFFECT_DURATION)
            led_array.stop_effect()
            
            print(f"3. Rainbow rows effect ({DEMO_EFFECT_DURATION} seconds)...")
            led_array.rainbow_rows(update_interval=0.2)
            time.sleep(DEMO_EFFECT_DURATION)
            led_array.stop_effect()
            
            print(f"4. Pulse effect ({DEMO_EFFECT_DURATION} seconds)...")
            led_array.pulse(base_hue=0.6, speed=1.0)
            time.sleep(DEMO_EFFECT_DURATION)
            led_array.stop_effect()
            
            print(f"5. Chase effect ({DEMO_EFFECT_DURATION} seconds)...")
            led_array.chase(speed=1.5)
            time.sleep(DEMO_EFFECT_DURATION)
            led_array.stop_effect()
            
        else:
            print(f"⚠ Need at least 24 LED channels for the 2x2 module layout")
            print(f"   Found only {len(LED_connectors)} channels")
        
        print("\nTurning off LEDs..")
        time.sleep(0.1)
        acc.set_values(LED_connectors, ["black"] * len(LED_connectors))
    
    print("Detaching..")
    acc.detach()
    print("Done")

