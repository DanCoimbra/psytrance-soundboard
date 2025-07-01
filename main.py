import tkinter as tk
from tkinter import ttk, messagebox
import pygame
import threading
import time
import os
import numpy as np
import requests
import json
import hashlib
from typing import List, Dict, Optional
from pathlib import Path
import tempfile
import shutil
from dotenv import load_dotenv

load_dotenv()

class FreesoundDownloader:
    """Downloads samples from Freesound.org using their API."""
    
    def __init__(self):
        self.base_url = "https://freesound.org/apiv2"
        # This is a demo token - for production, get your own at freesound.org/apiv2/apply/
        self.api_token = os.getenv("FREESOUND_API_TOKEN")  # Limited functionality, but works for basic searches
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {self.api_token}',
            'User-Agent': 'PsytranceSequencer/1.0'
        })
        
    def search_samples(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search for samples on Freesound."""
        try:
            params = {
                'query': query,
                'page_size': max_results,
                'fields': 'id,name,previews,download,license,username,duration',
                'filter': 'duration:[0.1 TO 3.0]'  # Short samples only
            }
            
            response = self.session.get(f"{self.base_url}/search/text/", params=params)
            if response.status_code == 200:
                data = response.json()
                return data.get('results', [])
            else:
                print(f"Search failed: {response.status_code}")
                return []
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def download_sample(self, sample_id: str, preview_url: str, filename: str) -> bool:
        """Download a sample preview (no API key required for previews)."""
        try:
            # Use preview URL for demo (full downloads need API key)
            response = self.session.get(preview_url, timeout=30)
            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    f.write(response.content)
                return True
            return False
        except Exception as e:
            print(f"Download error: {e}")
            return False

class SampleManager:
    """Manages sample downloads and caching."""
    
    def __init__(self):
        self.cache_dir = Path("samples_cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.downloader = FreesoundDownloader()
        self.sample_queries = {
            'kick': 'electronic kick drum techno',
            'hihat': 'electronic hihat closed techno',
            'snare': 'electronic snare clap techno',
            'bass_lead': 'psytrance bass lead wobble',
            'sub_bass': 'sub bass electronic deep',
            'acid_bass': 'acid bass squelch tb303',
            'perc1': 'electronic percussion tribal',
            'perc2': 'electronic percussion techno'
        }
        
    def get_sample_path(self, track_name: str) -> Optional[str]:
        """Get the path to a cached sample, downloading if necessary."""
        cache_file = self.cache_dir / f"{track_name}.mp3"
        
        if cache_file.exists():
            return str(cache_file)
        
        # Try to download
        query = self.sample_queries.get(track_name, f"electronic {track_name}")
        samples = self.downloader.search_samples(query, max_results=5)
        
        for sample in samples:
            if 'previews' in sample and 'preview-hq-mp3' in sample['previews']:
                preview_url = sample['previews']['preview-hq-mp3']
                if self.downloader.download_sample(sample['id'], preview_url, str(cache_file)):
                    print(f"Downloaded {track_name}: {sample['name']} by {sample.get('username', 'Unknown')}")
                    return str(cache_file)
        
        print(f"Could not download sample for {track_name}")
        return None
    
    def download_all_samples(self) -> Dict[str, str]:
        """Download all required samples."""
        samples = {}
        print("Downloading samples from Freesound.org...")
        
        for track_name in self.sample_queries.keys():
            path = self.get_sample_path(track_name)
            if path:
                samples[track_name] = path
        
        print(f"Downloaded {len(samples)} samples")
        return samples

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
            {"name": "Kick Drum", "color": "#FF4444", "file": None, "key": "kick"},
            {"name": "Hi-Hat", "color": "#44FF44", "file": None, "key": "hihat"},
            {"name": "Snare/Clap", "color": "#FFFF44", "file": None, "key": "snare"},
            {"name": "Bass Lead", "color": "#FF44FF", "file": None, "key": "bass_lead"},
            {"name": "Sub Bass", "color": "#8844FF", "file": None, "key": "sub_bass"},
            {"name": "Acid Bass", "color": "#44FFFF", "file": None, "key": "acid_bass"},
            {"name": "Perc 1", "color": "#FF8844", "file": None, "key": "perc1"},
            {"name": "Perc 2", "color": "#88FF44", "file": None, "key": "perc2"}
        ]
        
        # Initialize components
        self.sample_manager = SampleManager()
        self.audio_manager = AudioManager()
        self.ui_manager = UIManager(self.root, self.tracks, self.grid_size)
        self.sequencer_engine = SequencerEngine(self.beat_duration)
        
        # Load samples
        self.load_samples()
        
        # Connect UI callbacks
        self.ui_manager.set_play_callback(self.toggle_playback)
        self.ui_manager.set_clear_callback(self.clear_pattern)
        self.ui_manager.set_tempo_callback(self.set_tempo)
        
        # Start the sequencer thread
        self.sequencer_thread = threading.Thread(target=self.sequencer_loop, daemon=True)
        self.sequencer_thread.start()
    
    def setup_window(self):
        """Configure the main window."""
        self.root.title("Psytrance Beat Sequencer - Freesound Edition")
        self.root.geometry("1200x650")
        self.root.configure(bg="#1a1a1a")
        self.root.resizable(False, False)
    
    def load_samples(self):
        """Load samples from Freesound or generate synthetic ones as fallback."""
        try:
            # Show loading message
            loading_window = tk.Toplevel(self.root)
            loading_window.title("Loading Samples")
            loading_window.geometry("400x100")
            loading_window.configure(bg="#1a1a1a")
            loading_label = tk.Label(
                loading_window,
                text="Downloading samples from Freesound.org...",
                fg="white",
                bg="#1a1a1a",
                font=("Arial", 12)
            )
            loading_label.pack(expand=True)
            loading_window.update()
            
            # Try to download samples
            downloaded_samples = self.sample_manager.download_all_samples()
            
            # Load downloaded samples
            for track in self.tracks:
                key = track["key"]
                if key in downloaded_samples:
                    self.audio_manager.load_sample_file(track["key"], downloaded_samples[key])
                    track["file"] = downloaded_samples[key]
                else:
                    # Fallback to synthetic
                    self.generate_synthetic_sample(track)
            
            loading_window.destroy()
            
            # Show success message
            if downloaded_samples:
                messagebox.showinfo(
                    "Samples Loaded",
                    f"Successfully loaded {len(downloaded_samples)} samples from Freesound.org!\n"
                    f"Remaining tracks use synthetic sounds."
                )
            else:
                messagebox.showwarning(
                    "Offline Mode",
                    "Could not connect to Freesound.org.\nUsing synthetic sounds only."
                )
                
        except Exception as e:
            print(f"Error loading samples: {e}")
            # Fallback to all synthetic
            for track in self.tracks:
                self.generate_synthetic_sample(track)
    
    def generate_synthetic_sample(self, track):
        """Generate a synthetic sample for a track."""
        sample_rate = 44100
        track_name = track["key"]
        
        if track_name == "kick":
            sound_data = self.generate_kick(sample_rate)
        elif track_name == "hihat":
            sound_data = self.generate_hihat(sample_rate)
        elif track_name == "snare":
            sound_data = self.generate_snare(sample_rate)
        elif track_name == "bass_lead":
            sound_data = self.generate_wobbly_bass(sample_rate, freq=55)
        elif track_name == "sub_bass":
            sound_data = self.generate_sub_bass(sample_rate, freq=30)
        elif track_name == "acid_bass":
            sound_data = self.generate_acid_bass(sample_rate, freq=80)
        else:  # percussion
            freq = 200 if track_name == "perc1" else 150
            sound_data = self.generate_percussion(sample_rate, freq=freq)
        
        self.audio_manager.load_sound_data(track_name, sound_data, sample_rate)
    
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
                        track_key = self.tracks[track_idx]["key"]
                        self.audio_manager.play_sound(track_key)
                
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
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
    
    def load_sound_data(self, track_id: str, sound_data: np.ndarray, sample_rate: int):
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
    
    def load_sample_file(self, track_id: str, file_path: str):
        """Load a sound from file."""
        try:
            sound = pygame.mixer.Sound(file_path)
            self.sounds[track_id] = sound
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    
    def play_sound(self, track_id: str):
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
        title_label.pack(pady=(0, 10))
        
        # Subtitle
        subtitle_label = tk.Label(
            main_frame,
            text="Powered by Freesound.org",
            font=("Arial", 12),
            fg="#888888",
            bg="#1a1a1a"
        )
        subtitle_label.pack(pady=(0, 20))
        
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
        print("🎵 Starting Psytrance Beat Sequencer...")
        print("🔍 This version downloads real samples from Freesound.org!")
        print("📁 Samples will be cached locally for faster startup next time.")
        print("🎛️ If internet is unavailable, synthetic sounds will be used.")
        print("")
        
        app = PsytranceSequencer()
        app.run()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()