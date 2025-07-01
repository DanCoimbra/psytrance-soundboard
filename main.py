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
        # Load API token from environment variable
        self.api_token = os.getenv('FREESOUND_API_KEY')
        if not self.api_token:
            print("⚠️ Warning: FREESOUND_API_KEY not found in environment variables")
            self.api_token = "YOUR_API_KEY_HERE"  # Fallback for development
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {self.api_token}',
            'User-Agent': 'PsytranceSequencer/1.0'
        })
        
    def search_samples(self, query: str) -> List[Dict]:
        """
        Search for the single best sample on Freesound.
        It now requests only the first result and filters for usable licenses.
        """
        try:
            params = {
                'query': query,
                'page_size': 1,  # API Efficiency: Only get the top result.
                'fields': 'id,name,previews,download,license,username,duration',
                # API Filter: Ensure short samples and a permissive license.
                'filter': 'duration:[0.1 TO 3.0] license:"Creative Commons 0"' 
            }
            
            response = self.session.get(f"{self.base_url}/search/text/", params=params)
            
            if response.status_code == 401:
                print(f"❌ API Authentication failed. Please check your FREESOUND_API_KEY environment variable.")
                print(f"ℹ️ Get your API key at: https://freesound.org/apiv2/apply/")
                return []
            
            response.raise_for_status() # Raise an exception for other bad status codes (4xx or 5xx)

            data = response.json()
            return data.get('results', [])

        except requests.exceptions.RequestException as e:
            if "401" in str(e):
                print(f"❌ API Authentication failed for query '{query}'")
                print(f"ℹ️ Get your API key at: https://freesound.org/apiv2/apply/")
            else:
                print(f"🔍 Search failed for query '{query}': {e}")
            return []
        except Exception as e:
            print(f"❌ An unexpected error occurred during search: {e}")
            return []
    
    def download_sample(self, sample_id: str, preview_url: str, filename: str) -> bool:
        """Download a sample preview (no API key required for previews)."""
        try:
            # Use preview URL for demo (full downloads need a real API key)
            response = self.session.get(preview_url, timeout=30)
            response.raise_for_status()
            
            with open(filename, 'wb') as f:
                f.write(response.content)
            return True

        except requests.exceptions.RequestException as e:
            print(f"Download error for sample {sample_id}: {e}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred during download: {e}")
            return False

class SampleManager:
    """Manages sample downloads and caching."""
    
    def __init__(self):
        self.cache_dir = Path("samples_cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.downloader = FreesoundDownloader()

    sample_queries = {
        'bass_lead': 'Psy-Trance Kick Bass Bassline Pattern Loop 142bpm',
        'acid_bass': '140 BPM TB-303 like acid bassline with kick loop',
        'tribal_bass': 'Epic Tribal Drums',
        'psy_squelch': 'Psy Squelch 01',
        'wobbly_bass': 'Dubstep Wobbly Bass17',
        'deep_tribal': 'Tribal Drum Beat - Drum Africa',
        'kick': 'psytrance kick',
        'sub_bass': 'Pure Psytrance Kicks 00-20',
    }
        
    def get_sample_path(self, track_name: str) -> Optional[str]:
        """Get the path to a cached sample, downloading if necessary."""
        cache_file = self.cache_dir / f"{track_name}.mp3"
        
        if cache_file.exists():
            return str(cache_file)
        
        # Try to download with the primary query first.
        query = self.sample_queries.get(track_name, f"electronic {track_name}")
        # The search method now correctly asks for only the first result.
        samples = self.downloader.search_samples(query)
        
        # If first search fails, try alternative searches
        if not samples:
            alternative_queries = {
                'bass_lead': ['SYNDRM psytrance bass', 'psy trance bassline 142bpm', 'psytrance kick bass'],
                'acid_bass': ['TB-303 acid bassline', 'Deconstructed TB303 loop', 'acid bass 140 bpm'],
                'tribal_bass': ['tribal drums epic', 'cinematic tribal drums', 'african drums'],
                'psy_squelch': ['kapnos_mantis squelch', 'psychedelic squelch', 'psy fx'],
                'wobbly_bass': ['wobbly bass 140', 'dubstep bass wobble', 'bass wobble'],
                'deep_tribal': ['peridactyloptrix tribal', 'tribal drum beat', 'deep tribal']
            }
            
            for alt_query in alternative_queries.get(track_name, []):
                # We only need the first result, so the method is simpler.
                samples = self.downloader.search_samples(alt_query)
                if samples:
                    break
        
        # This loop will now run at most once, as `samples` contains 0 or 1 items.
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
        self.master_volume = 1.0  # Increased from 0.8 to maximum
        
        # Track definitions - All bass, no high frequencies!
        self.tracks = [
            {"name": "Kick Drum", "color": "#FF4444", "file": None, "key": "kick"},
            {"name": "Bass Lead", "color": "#FF44FF", "file": None, "key": "bass_lead"},
            {"name": "Acid Bass", "color": "#44FFFF", "file": None, "key": "acid_bass"},
            {"name": "Sub Bass", "color": "#8844FF", "file": None, "key": "sub_bass"},
            {"name": "Tribal Bass", "color": "#FF8844", "file": None, "key": "tribal_bass"},
            {"name": "Psychedelic Squelch", "color": "#88FF44", "file": None, "key": "psy_squelch"},
            {"name": "Wobbly Bass", "color": "#FFAA44", "file": None, "key": "wobbly_bass"},
            {"name": "Deep Tribal", "color": "#AA44FF", "file": None, "key": "deep_tribal"}
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
        self.ui_manager.set_volume_callback(self.set_volume)
        
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
                text="Downloading samples from Freesound.org...\nThis may take a moment...",
                fg="white",
                bg="#1a1a1a",
                font=("Arial", 12)
            )
            loading_label.pack(expand=True)
            loading_window.update()
            
            # Check API key status
            if self.sample_manager.downloader.api_token == "YOUR_API_KEY_HERE":
                messagebox.showwarning(
                    "API Key Not Found",
                    "⚠️ No Freesound API key found in environment variables.\n\n"
                    "To use real samples:\n"
                    "1. Get your API key at freesound.org/apiv2/apply/\n"
                    "2. Set FREESOUND_API_KEY in your environment variables\n"
                    "3. Restart the application\n\n"
                    "🎹 For now, using synthetic sounds..."
                )
                loading_window.destroy()
                return
            
            # Try to download samples
            downloaded_samples = self.sample_manager.download_all_samples()
            
            # Load downloaded samples and generate synthetic for missing ones
            for track in self.tracks:
                key = track["key"]
                if key in downloaded_samples:
                    # Successfully downloaded - load the file
                    self.audio_manager.load_sample_file(key, downloaded_samples[key])
                    track["file"] = downloaded_samples[key]
                    print(f"✅ Loaded downloaded sample: {track['name']}")
                else:
                    # Download failed - inform user (no synthetic fallback)
                    print(f"❌ Could not download sample: {track['name']}")
                    track["file"] = None
            
            loading_window.destroy()
            
            # Show summary message
            downloaded_count = len(downloaded_samples)
            missing_count = len(self.tracks) - downloaded_count
            
            if downloaded_count > 0:
                message = f"✅ Successfully loaded {downloaded_count} real samples from Freesound.org!\n"
                if missing_count > 0:
                    message += f"❌ {missing_count} samples failed to download.\n\n"
                message += "🎵 Ready to make some psytrance beats!"
                messagebox.showinfo("Samples Loaded", message)
            else:
                messagebox.showwarning(
                    "No Samples Downloaded",
                    "❌ Could not download any samples from Freesound.org.\n"
                    "🔑 Please check your API key and internet connection.\n\n"
                    "🔄 Try restarting the app after fixing the issues."
                )
                
        except Exception as e:
            print(f"Error loading samples: {e}")
            # No fallback - user must have working samples
            print("❌ Unable to load any samples...")
            messagebox.showerror(
                "Sample Loading Failed", 
                "❌ Could not load samples from Freesound.org.\n"
                "🔑 Please check your API key and internet connection.\n\n"
                "🔄 Restart the app to retry."
            )
    
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
            # Enhanced wobbly bass for psytrance lead
            sound_data = self.generate_enhanced_wobbly_bass(sample_rate, freq=55)
        elif track_name == "sub_bass":
            sound_data = self.generate_sub_bass(sample_rate, freq=30)
        elif track_name == "acid_bass":
            # Enhanced acid bass with more character
            sound_data = self.generate_enhanced_acid_bass(sample_rate, freq=80)
        elif track_name == "perc1":
            # Tribal-style percussion
            sound_data = self.generate_tribal_percussion(sample_rate)
        else:  # perc2
            freq = 150
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
        click = np.exp(-t * 50) * np.sin(2 * np.pi * 2000 * t) * 0.5
        kick += click
        
        return kick * 0.95
    
    def generate_hihat(self, sample_rate: int) -> np.ndarray:
        """Generate a subtle, bass-heavy hi-hat."""
        duration = 0.08
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Less harsh noise, more filtered
        noise = np.random.normal(0, 0.05, len(t))
        
        # Add some low-mid frequency content
        metallic = np.sin(2 * np.pi * 2000 * t) * 0.2
        lowmid = np.sin(2 * np.pi * 400 * t) * 0.3
        
        # Combine with emphasis on lower frequencies
        hihat = (noise + metallic + lowmid) * np.exp(-t * 25)
        
        return hihat * 0.4
    
    def generate_snare(self, sample_rate: int) -> np.ndarray:
        """Generate a minimal, bass-heavy snare/clap."""
        duration = 0.12
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Much less noise, more tonal
        noise = np.random.normal(0, 0.05, len(t))
        
        # Deep tonal component
        tone = np.sin(2 * np.pi * 120 * t) * 0.6
        midtone = np.sin(2 * np.pi * 240 * t) * 0.3
        
        # Combine with heavy low-end emphasis
        snare = (noise + tone + midtone) * np.exp(-t * 15)
        
        return snare * 0.5
    
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
        
        return sub_bass * 0.95
    
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
    
    def generate_enhanced_wobbly_bass(self, sample_rate: int, freq: float) -> np.ndarray:
        """Generate massive wobbly psytrance bass lead."""
        duration = 0.8
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Deep fundamental frequency
        base_freq = freq
        
        # Complex wobble pattern
        wobble1 = 3.2 * np.sin(2 * np.pi * 2.5 * t)
        wobble2 = 1.8 * np.sin(2 * np.pi * 1.3 * t + np.pi/3)
        total_wobble = 1 + 0.6 * np.sin(wobble1 + wobble2)
        
        freq_mod = base_freq * total_wobble
        
        # Multiple bass layers for massive sound
        bass1 = np.sin(2 * np.pi * freq_mod * t)
        bass2 = np.sin(2 * np.pi * freq_mod * 0.5 * t) * 0.8
        bass3 = np.sin(2 * np.pi * freq_mod * 2 * t) * 0.5
        bass4 = np.sin(2 * np.pi * freq_mod * 1.5 * t) * 0.4
        
        # Combine all layers
        bass = bass1 + bass2 + bass3 + bass4
        
        # Heavy filter modulation
        filter_freq = 2.0 + 1.5 * np.sin(2 * np.pi * 3.1 * t + np.pi/4)
        bass *= 0.4 + 0.6 * np.sin(filter_freq)
        
        # Saturation for grit
        bass = np.tanh(bass * 3.5) * 0.95
        
        # Long sustain envelope
        attack = np.minimum(t * 40, 1.0)
        sustain = np.exp(-np.maximum(t - 0.2, 0) * 1.2)
        envelope = attack * sustain
        bass *= envelope
        
        return bass * 0.95
    
    def generate_enhanced_acid_bass(self, sample_rate: int, freq: float) -> np.ndarray:
        """Generate massive acid bass with serious low-end."""
        duration = 0.6
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Rich sawtooth with multiple harmonics
        phase = 2 * np.pi * freq * t
        acid = np.sin(phase)
        for h in range(2, 8):
            acid += (1.2 / h) * np.sin(h * phase)
        
        # Add sub-octave for massive low-end
        sub_octave = np.sin(np.pi * freq * t) * 0.9
        acid += sub_octave
        
        # Complex filter sweep
        cutoff = 2.0 + 3.0 * np.exp(-t * 6) * np.sin(2 * np.pi * 4.5 * t)
        filter_mod = 0.3 + 0.7 * np.sin(cutoff)
        acid *= filter_mod
        
        # Heavy resonance
        resonance = np.sin(2 * np.pi * freq * 4 * t) * 0.5 * filter_mod
        acid += resonance
        
        # Aggressive saturation
        acid = np.tanh(acid * 4.5) * 0.95
        
        # Punchy envelope
        attack = np.minimum(t * 50, 1.0)
        decay = np.exp(-np.maximum(t - 0.05, 0) * 4)
        envelope = attack * decay
        acid *= envelope
        
        return acid * 0.95
    
    def generate_tribal_percussion(self, sample_rate: int) -> np.ndarray:
        """Generate deep, bass-heavy tribal percussion."""
        duration = 0.3
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Deep tom with pitch sweep
        base_freq = 80  # Much lower frequency
        freq_sweep = base_freq * np.exp(-t * 6)
        tom = np.sin(2 * np.pi * freq_sweep * t)
        
        # Add sub-bass component
        sub = np.sin(2 * np.pi * freq_sweep * 0.5 * t) * 0.6
        
        # Minimal high-frequency content
        click = np.sin(2 * np.pi * 1000 * t) * 0.1 * np.exp(-t * 30)
        
        # Very little noise
        noise = np.random.normal(0, 0.03, len(t))
        
        # Combine with heavy low-end emphasis
        perc = tom + sub + click + noise
        
        # Punchy envelope
        envelope = np.exp(-t * 8) * (1 - np.exp(-t * 60))
        perc *= envelope
        
        return perc * 0.7
    
    def generate_percussion(self, sample_rate: int, freq: float) -> np.ndarray:
        """Generate bass-heavy electronic percussion."""
        duration = 0.25
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Lower pitched percussion
        base_freq = freq * 0.5  # Much lower
        perc = np.sin(2 * np.pi * base_freq * t)
        
        # Add sub-harmonic
        sub = np.sin(2 * np.pi * base_freq * 0.5 * t) * 0.5
        
        # Minimal noise
        noise = np.random.normal(0, 0.05, len(t))
        
        # Combine
        perc = perc + sub + noise
        
        # Envelope
        envelope = np.exp(-t * 10)
        perc *= envelope
        
        return perc * 0.6
    
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
                        # Only play if the sample was successfully loaded
                        if self.tracks[track_idx]["file"] is not None:
                            self.audio_manager.play_sound(track_key, self.master_volume)
                
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
    
    def set_volume(self, volume: float):
        """Set the master volume."""
        self.master_volume = max(0.0, min(1.0, volume))  # Clamp between 0 and 1
    
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
    
    def play_sound(self, track_id: str, volume: float = 0.8):
        """Play a sound with the given volume."""
        if track_id in self.sounds:
            sound = self.sounds[track_id]
            # Scale volume exponentially for better control
            scaled_volume = (volume ** 2) * 1.5  # Increased volume scaling
            sound.set_volume(min(scaled_volume, 1.0))  # Ensure we don't exceed 1.0
            sound.play()


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
        self.volume_callback = None
        
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
        """Create control panel with play/stop, clear, tempo and volume controls."""
        control_frame = ttk.Frame(parent)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        # Play/Stop button
        self.play_button = ttk.Button(control_frame, text="▶ Play", command=self.on_play_clicked)
        self.play_button.pack(side=tk.LEFT, padx=5)
        
        # Clear button
        clear_button = ttk.Button(control_frame, text="Clear", command=self.on_clear_clicked)
        clear_button.pack(side=tk.LEFT, padx=5)
        
        # Volume control
        volume_frame = ttk.Frame(control_frame)
        volume_frame.pack(side=tk.LEFT, padx=20)
        
        volume_label = ttk.Label(volume_frame, text="Volume:")
        volume_label.pack(side=tk.LEFT)
        
        self.volume_slider = ttk.Scale(
            volume_frame,
            from_=0,
            to=200,  # Increased from 100 to 200 for more volume range
            orient=tk.HORIZONTAL,
            length=150,
            command=self.on_volume_changed
        )
        self.volume_slider.set(100)  # Default to middle
        self.volume_slider.pack(side=tk.LEFT, padx=5)
    
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
    
    def on_volume_changed(self, value):
        """Handle volume slider changes."""
        try:
            volume = float(value) / 200.0  # Adjusted for new slider range
            if self.volume_callback:
                self.volume_callback(volume)
        except ValueError:
            print(f"Invalid volume value: {value}")
    
    def set_volume_callback(self, callback):
        """Set the volume change callback."""
        self.volume_callback = callback
    
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
        
        sequencer = PsytranceSequencer()
        sequencer.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        print("🔄 Please restart the application.")


if __name__ == "__main__":
    main()