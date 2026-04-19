# -*- encoding: utf-8 -*-
"""音效管理器 — 纯播放逻辑，不包含任何触发条件

触发逻辑由外部调用者决定（射击、受伤、死亡等），
本组件只负责：加载音效资源 + 播放。
"""

import ue


class AudioManager:
    """音效管理器

    用法:
        audio = AudioManager(owner)
        audio.play_gunshot(location)
        audio.play_hit(location)
        audio.play_bgm()
    """

    # ── 音效资源路径 ──
    SOUND_PATHS = {
        "gunshot":       "/Game/StarterContent/Audio/Fire01_Cue.Fire01_Cue",
        "magic_arrow":   "/Game/StarterContent/Audio/Light02_Cue.Light02_Cue",
        "enemy_hit":     "/Game/StarterContent/Audio/Explosion_Cue.Explosion_Cue",
        "enemy_death":   "/Game/StarterContent/Audio/Explosion01.Explosion01",
        "enemy_attack":  "/Game/StarterContent/Audio/Collapse_Cue.Collapse_Cue",
        "bgm":           "/Game/StarterContent/Audio/Starter_Music_Cue.Starter_Music_Cue",
    }

    # ── 粒子特效路径 ──
    PARTICLE_PATHS = {
        "muzzle_flash":  "/Game/StarterContent/Particles/P_Explosion.P_Explosion",
        "hit_explosion": "/Game/StarterContent/Particles/P_Explosion.P_Explosion",
        "magic_fire":    "/Game/StarterContent/Particles/P_Fire.P_Fire",
    }

    def __init__(self, owner):
        self.owner = owner
        self._sounds = {}       # 缓存已加载的 SoundCue
        self._particles = {}    # 缓存已加载的 NiagaraSystem/ParticleSystem
        self._bgm_component = None

    def _load_sound(self, key: str):
        """加载并缓存音效资源"""
        if key in self._sounds:
            return self._sounds[key]
        path = self.SOUND_PATHS.get(key)
        if not path:
            return None
        sound = ue.LoadObject(ue.SoundBase, path)
        if sound:
            self._sounds[key] = sound
        else:
            ue.LogWarning(f"AudioManager: Failed to load sound '{key}' from {path}")
        return sound

    def _load_particle(self, key: str):
        """加载并缓存粒子特效资源"""
        if key in self._particles:
            return self._particles[key]
        path = self.PARTICLE_PATHS.get(key)
        if not path:
            return None
        particle = ue.LoadObject(ue.ParticleSystem, path)
        if particle:
            self._particles[key] = particle
        else:
            ue.LogWarning(f"AudioManager: Failed to load particle '{key}' from {path}")
        return particle

    def _play_sound_at(self, sound_key: str, location, volume: float = 1.0):
        """在指定位置播放3D音效"""
        sound = self._load_sound(sound_key)
        if not sound:
            return
        world = self.owner.GetWorld()
        if world:
            ue.GameplayStatics.PlaySoundAtLocation(
                world, sound, location,
                ue.Rotator(0.0, 0.0, 0.0),
                volume, 1.0, 0.0
            )

    def _play_sound_2d(self, sound_key: str, volume: float = 1.0):
        """播放2D音效（无空间感，适合BGM/UI音）"""
        sound = self._load_sound(sound_key)
        if not sound:
            return
        world = self.owner.GetWorld()
        if world:
            ue.GameplayStatics.PlaySound2D(
                world, sound,
                volume, 1.0, 0.0
            )

    def _spawn_particle_at(self, particle_key: str, location, scale: float = 1.0):
        """在指定位置生成粒子特效"""
        particle = self._load_particle(particle_key)
        if not particle:
            return
        world = self.owner.GetWorld()
        if not world:
            return
        ue.GameplayStatics.SpawnEmitterAtLocation(
            world, particle, location,
            ue.Rotator(0.0, 0.0, 0.0),
            ue.Vector(scale, scale, scale),
            True  # bAutoDestroy
        )

    # ── 对外播放接口（触发由调用方决定） ──

    def play_gunshot(self, location):
        """播放射击音效 + 枪口火花"""
        self._play_sound_at("gunshot", location, 0.6)
        self._spawn_particle_at("muzzle_flash", location, 0.2)

    def play_magic_arrow(self, location):
        """播放魔法箭音效"""
        self._play_sound_at("magic_arrow", location, 0.8)

    def play_enemy_hit(self, location):
        """播放敌人受击音效 + 爆炸特效"""
        self._play_sound_at("enemy_hit", location, 0.7)
        self._spawn_particle_at("hit_explosion", location, 0.3)

    def play_enemy_death(self, location):
        """播放敌人死亡音效 + 爆炸特效"""
        self._play_sound_at("enemy_death", location, 0.8)
        self._spawn_particle_at("hit_explosion", location, 0.5)

    def play_enemy_attack(self, location):
        """播放敌人攻击音效"""
        self._play_sound_at("enemy_attack", location, 0.5)

    def play_bgm(self):
        """播放背景音乐（2D循环）"""
        self._play_sound_2d("bgm", 0.3)
