import tkinter as tk
from tkinter import ttk
import pygame
import threading
import time
import os
import numpy as np
from typing import List, Dict, Optional

class PsytranceSequencer:
    """Main application class for the Psytrance Beat Sequencer."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        
        # Sequencer parameters
        self.bpm = 145  # Classic psytrance tempo
        self.beat_duration = 60.0 / self.bpm / 4  # 16th note duration
        self.grid_size = (16, 8)  # 16 time slices, 8 tracks
        self.current_step = 0
        self.is_playing = False
        
        # Track definitions
        self.tracks = [
            {"name": "Kick Drum", "color": "#FF4444", "file": None},
            {"name": "Hi-Hat", "color": "#44FF44", "file": None},
            {"name": "Snare/Clap", "color": "#FFFF44", "file": None},
            {"name": "Bass Lead", "color": "#FF44FF", "file": None},
            {"name": "Sub Bass", "color": "#8844FF", "file": None},
            {"name": "Acid Bass", "color": "#44FFFF", "file": None},
            {"name": "Perc 1", "color": "#FF8844", "file": None},
            {"name": "Perc 2", "color": "#88FF44", "file": None}
        ]
        
        # Initialize audio and UI
        self.audio_manager = AudioManager()
        self.ui_manager = UIManager(self.root, self.tracks, self.grid_size)
        self.sequencer_engine = SequencerEngine(self.beat_duration)
        
        # Generate synthetic sounds
        self.generate_sounds()
        
        # Connect UI callbacks
        self.ui_manager.set_play_callback(self.toggle_playback)
        self.ui_manager.set_clear_callback(self.clear_pattern)
        self.ui_manager.set_tempo_callback(self.set_tempo)
        
        # Start the sequencer thread
        self.sequencer_thread = threading.Thread(target=self.sequencer_loop, daemon=True)
        self.sequencer_thread.start()
    
    def setup_window(self):
        """Configure the main window."""
        self.root.title("Psytrance Beat Sequencer")
        self.root.geometry("1200x600")
        self.root.configure(bg="#1a1a1a")
        self.root.resizable(False, False)
    
    def generate_sounds(self):
        """Generate synthetic psytrance sounds."""
        sample_rate = 44100
        
        # Generate different sound types
        sounds = {
            0: self.generate_kick(sample_rate),
            1: self.generate_hihat(sample_rate),
            2: self.generate_snare(sample_rate),
            3: self.generate_wobbly_bass(sample_rate, freq=55),  # Wobbly bass lead
            4: self.generate_sub_bass(sample_rate, freq=30),     # Sub bass
            5: self.generate_acid_bass(sample_rate, freq=80),    # Acid bass
            6: self.generate_percussion(sample_rate, freq=200),  # Perc 1
            7: self.generate_percussion(sample_rate, freq=150)   # Perc 2
        }
        
        # Load sounds into audio manager
        for track_idx, sound_data in sounds.items():
            self.audio_manager.load_sound(track_idx, sound_data, sample_rate)
    
    def generate_kick(self, sample_rate: int) -> np.ndarray:
        """Generate a punchy kick drum."""
        duration = 0.3
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Frequency sweep from 60Hz to 40Hz
        freq = 60 * np.exp(-t * 8)
        kick = np.sin(2 * np.pi * freq * t)
        
        # Envelope
        envelope = np.exp(-t * 15)
        kick *= envelope
        
        # Add click for punch
        click = np.exp(-t * 50) * np.sin(2 * np.pi * 2000 * t) * 0.3
        kick += click
        
        return kick * 0.8
    
    def generate_hihat(self, sample_rate: int) -> np.ndarray:
        """Generate a crisp hi-hat."""
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # White noise
        noise = np.random.normal(0, 0.1, len(t))
        
        # High-pass filter effect (emphasize high frequencies)
        hihat = noise * np.exp(-t * 20)
        
        # Add some metallic ring
        ring = np.sin(2 * np.pi * 8000 * t) * np.exp(-t * 30) * 0.2
        hihat += ring
        
        return hihat * 0.6
    
    def generate_snare(self, sample_rate: int) -> np.ndarray:
        """Generate a snare/clap sound."""
        duration = 0.15
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Noise component
        noise = np.random.normal(0, 0.1, len(t))
        
        # Tonal component
        tone = np.sin(2 * np.pi * 200 * t) * 0.3
        
        # Combine and shape
        snare = (noise + tone) * np.exp(-t * 12)
        
        return snare * 0.7
    
    def generate_wobbly_bass(self, sample_rate: int, freq: float) -> np.ndarray:
        """Generate the signature wobbly psytrance bass."""
        duration = 0.5
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Base frequency
        base_freq = freq
        
        # Wobble modulation (elegant, not too aggressive)
        wobble_freq = 2.5  # Hz
        wobble_depth = 0.3
        freq_mod = base_freq * (1 + wobble_depth * np.sin(2 * np.pi * wobble_freq * t))
        
        # Generate the bass tone
        bass = np.sin(2 * np.pi * freq_mod * t)
        
        # Add harmonics for richness
        bass += 0.3 * np.sin(2 * np.pi * freq_mod * 2 * t)
        bass += 0.1 * np.sin(2 * np.pi * freq_mod * 3 * t)
        
        # Filter modulation for that "round" texture
        filter_mod = 0.5 + 0.5 * np.sin(2 * np.pi * wobble_freq * 1.3 * t)
        bass *= filter_mod
        
        # Envelope
        envelope = np.exp(-t * 2) * (1 - np.exp(-t * 20))
        bass *= envelope
        
        return bass * 0.6
    
    def generate_sub_bass(self, sample_rate: int, freq: float) -> np.ndarray:
        """Generate deep sub bass."""
        duration = 0.8
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Deep sine wave with slight modulation
        mod = 1 + 0.1 * np.sin(2 * np.pi * 1.5 * t)
        sub_bass = np.sin(2 * np.pi * freq * mod * t)
        
        # Envelope
        envelope = np.exp(-t * 1.5) * (1 - np.exp(-t * 10))
        sub_bass *= envelope
        
        return sub_bass * 0.8
    
    def generate_acid_bass(self, sample_rate: int, freq: float) -> np.ndarray:
        """Generate squelchy acid bass."""
        duration = 0.3
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Sawtooth-like wave
        phase = 2 * np.pi * freq * t
        acid = np.sin(phase) + 0.3 * np.sin(2 * phase) + 0.1 * np.sin(3 * phase)
        
        # Filter sweep
        filter_sweep = 0.3 + 0.7 * np.exp(-t * 8)
        acid *= filter_sweep
        
        # Envelope
        envelope = np.exp(-t * 10) * (1 - np.exp(-t * 30))
        acid *= envelope
        
        return acid * 0.5
    
    def generate_percussion(self, sample_rate: int, freq: float) -> np.ndarray:
        """Generate percussion sounds."""
        duration = 0.2
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Pitched percussion
        perc = np.sin(2 * np.pi * freq * t)
        
        # Add some noise
        noise = np.random.normal(0, 0.1, len(t))
        perc += noise * 0.3
        
        # Envelope
        envelope = np.exp(-t * 8)
        perc *= envelope
        
        return perc * 0.4
    
    def sequencer_loop(self):
        """Main sequencer loop running in a separate thread."""
        while True:
            if self.is_playing:
                # Get current pattern state
                pattern = self.ui_manager.get_pattern()
                
                # Play sounds for current step
                for track_idx in range(len(self.tracks)):
                    if pattern[self.current_step][track_idx]:
                        self.audio_manager.play_sound(track_idx)
                
                # Update UI
                self.ui_manager.update_playhead(self.current_step)
                
                # Advance to next step
                self.current_step = (self.current_step + 1) % 16
                
                # Wait for next beat
                time.sleep(self.beat_duration)
            else:
                time.sleep(0.01)  # Small delay when not playing
    
    def toggle_playback(self):
        """Toggle play/stop state."""
        self.is_playing = not self.is_playing
        if not self.is_playing:
            self.ui_manager.clear_playhead()
    
    def clear_pattern(self):
        """Clear all pattern data."""
        self.ui_manager.clear_pattern()
        self.current_step = 0
    
    def set_tempo(self, bpm: int):
        """Set the tempo."""
        self.bpm = bpm
        self.beat_duration = 60.0 / bpm / 4
    
    def run(self):
        """Start the application."""
        self.root.mainloop()


class AudioManager:
    """Handles audio playback using pygame."""
    
    def __init__(self):
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.init()
        self.sounds: Dict[int, pygame.mixer.Sound] = {}
    
    def load_sound(self, track_id: int, sound_data: np.ndarray, sample_rate: int):
        """Load a sound from numpy array."""
        # Convert to 16-bit integers
        sound_data = (sound_data * 32767).astype(np.int16)
        
        # Convert to stereo
        if len(sound_data.shape) == 1:
            stereo_data = np.column_stack((sound_data, sound_data))
        else:
            stereo_data = sound_data
        
        # Create pygame sound
        sound = pygame.sndarray.make_sound(stereo_data)
        self.sounds[track_id] = sound
    
    def play_sound(self, track_id: int):
        """Play a sound by track ID."""
        if track_id in self.sounds:
            self.sounds[track_id].play()


class UIManager:
    """Manages the user interface."""
    
    def __init__(self, root: tk.Tk, tracks: List[Dict], grid_size: tuple):
        self.root = root
        self.tracks = tracks
        self.grid_size = grid_size
        self.buttons = []
        self.pattern = [[False for _ in range(grid_size[1])] for _ in range(grid_size[0])]
        self.playhead_labels = []
        
        self.play_callback = None
        self.clear_callback = None
        self.tempo_callback = None
        
        self.create_ui()
    
    def create_ui(self):
        """Create the user interface."""
        # Main container
        main_frame = tk.Frame(self.root, bg="#1a1a1a")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = tk.Label(
            main_frame,
            text="PSYTRANCE BEAT SEQUENCER",
            font=("Arial", 24, "bold"),
            fg="#00ff88",
            bg="#1a1a1a"
        )
        title_label.pack(pady=(0, 20))
        
        # Control panel
        self.create_controls(main_frame)
        
        # Sequencer grid
        self.create_grid(main_frame)
    
    def create_controls(self, parent):
        """Create the control panel."""
        control_frame = tk.Frame(parent, bg="#1a1a1a")
        control_frame.pack(pady=(0, 20))
        
        # Play/Stop button
        self.play_button = tk.Button(
            control_frame,
            text="PLAY",
            font=("Arial", 14, "bold"),
            bg="#00ff88",
            fg="#1a1a1a",
            activebackground="#00cc66",
            width=8,
            command=self.on_play_clicked
        )
        self.play_button.pack(side="left", padx=(0, 10))
        
        # Clear button
        clear_button = tk.Button(
            control_frame,
            text="CLEAR",
            font=("Arial", 14, "bold"),
            bg="#ff4444",
            fg="white",
            activebackground="#cc3333",
            width=8,
            command=self.on_clear_clicked
        )
        clear_button.pack(side="left", padx=(0, 20))
        
        # Tempo control
        tempo_label = tk.Label(
            control_frame,
            text="BPM:",
            font=("Arial", 12, "bold"),
            fg="white",
            bg="#1a1a1a"
        )
        tempo_label.pack(side="left", padx=(0, 5))
        
        self.tempo_var = tk.StringVar(value="145")
        tempo_entry = tk.Entry(
            control_frame,
            textvariable=self.tempo_var,
            font=("Arial", 12),
            width=6,
            justify="center"
        )
        tempo_entry.pack(side="left")
        tempo_entry.bind("<Return>", self.on_tempo_changed)
    
    def create_grid(self, parent):
        """Create the sequencer grid."""
        grid_frame = tk.Frame(parent, bg="#2a2a2a", relief="raised", bd=2)
        grid_frame.pack()
        
        # Step numbers header
        header_frame = tk.Frame(grid_frame, bg="#2a2a2a")
        header_frame.grid(row=0, column=1, columnspan=16, sticky="ew")
        
        self.playhead_labels = []
        for step in range(16):
            label = tk.Label(
                header_frame,
                text=str(step + 1),
                font=("Arial", 10, "bold"),
                fg="#888888",
                bg="#2a2a2a",
                width=4
            )
            label.grid(row=0, column=step, padx=1, pady=5)
            self.playhead_labels.append(label)
        
        # Track rows
        self.buttons = []
        for track_idx, track in enumerate(self.tracks):
            # Track label
            track_label = tk.Label(
                grid_frame,
                text=track["name"],
                font=("Arial", 10, "bold"),
                fg=track["color"],
                bg="#2a2a2a",
                width=12,
                anchor="w"
            )
            track_label.grid(row=track_idx + 1, column=0, padx=10, pady=2, sticky="w")
            
            # Step buttons for this track
            track_buttons = []
            for step in range(16):
                button = tk.Button(
                    grid_frame,
                    width=4,
                    height=2,
                    bg="#3a3a3a",
                    activebackground="#4a4a4a",
                    relief="raised",
                    command=lambda t=track_idx, s=step: self.toggle_step(t, s)
                )
                button.grid(row=track_idx + 1, column=step + 1, padx=1, pady=1)
                track_buttons.append(button)
            
            self.buttons.append(track_buttons)
    
    def toggle_step(self, track: int, step: int):
        """Toggle a step in the pattern."""
        self.pattern[step][track] = not self.pattern[step][track]
        
        if self.pattern[step][track]:
            self.buttons[track][step].configure(bg=self.tracks[track]["color"])
        else:
            self.buttons[track][step].configure(bg="#3a3a3a")
    
    def update_playhead(self, current_step: int):
        """Update the playhead visualization."""
        def update():
            # Clear previous playhead
            for label in self.playhead_labels:
                label.configure(bg="#2a2a2a", fg="#888888")
            
            # Highlight current step
            self.playhead_labels[current_step].configure(bg="#00ff88", fg="#1a1a1a")
        
        self.root.after(0, update)
    
    def clear_playhead(self):
        """Clear the playhead visualization."""
        def clear():
            for label in self.playhead_labels:
                label.configure(bg="#2a2a2a", fg="#888888")
        
        self.root.after(0, clear)
    
    def get_pattern(self) -> List[List[bool]]:
        """Get the current pattern state."""
        return self.pattern
    
    def clear_pattern(self):
        """Clear the pattern and UI."""
        self.pattern = [[False for _ in range(self.grid_size[1])] for _ in range(self.grid_size[0])]
        
        for track_buttons in self.buttons:
            for button in track_buttons:
                button.configure(bg="#3a3a3a")
    
    def on_play_clicked(self):
        """Handle play button click."""
        if self.play_callback:
            self.play_callback()
        
        # Update button text
        current_text = self.play_button.cget("text")
        new_text = "STOP" if current_text == "PLAY" else "PLAY"
        self.play_button.configure(text=new_text)
    
    def on_clear_clicked(self):
        """Handle clear button click."""
        if self.clear_callback:
            self.clear_callback()
    
    def on_tempo_changed(self, event):
        """Handle tempo change."""
        try:
            bpm = int(self.tempo_var.get())
            if 60 <= bpm <= 200:  # Reasonable BPM range
                if self.tempo_callback:
                    self.tempo_callback(bpm)
        except ValueError:
            pass  # Invalid input, ignore
    
    def set_play_callback(self, callback):
        """Set the play button callback."""
        self.play_callback = callback
    
    def set_clear_callback(self, callback):
        """Set the clear button callback."""
        self.clear_callback = callback
    
    def set_tempo_callback(self, callback):
        """Set the tempo change callback."""
        self.tempo_callback = callback


class SequencerEngine:
    """Handles timing and sequencing logic."""
    
    def __init__(self, beat_duration: float):
        self.beat_duration = beat_duration
    
    def update_tempo(self, beat_duration: float):
        """Update the beat duration."""
        self.beat_duration = beat_duration


def main():
    """Main entry point."""
    try:
        app = PsytranceSequencer()
        app.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()