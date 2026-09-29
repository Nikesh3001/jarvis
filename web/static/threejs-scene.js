/**
 * FRIDAY 3D Holographic Spatial Engine
 * Powered by Three.js
 */

(function () {
  'use strict';

  if (typeof THREE === 'undefined') {
    console.error('Three.js library is not loaded');
    return;
  }

  // State
  let scene, camera, renderer, raycaster, mouse;
  let canvasContainer, canvas;
  let currentMode = 'reactor'; // 'reactor' | 'globe' | 'armor'
  let isStarkMode = true;
  let autoRotate = true;
  let rotateSpeed = 0.006;
  let explodeAmount = 0.0;
  let isSpeaking = false;
  let audioPulse = 0;
  let animationFrameId = null;

  // Groups
  let mainGroup = null;
  let reactorGroup = null;
  let globeGroup = null;
  let armorGroup = null;
  let particleSystem = null;
  let particleGeo = null;

  // Interactive Hotspots
  const hotspots = [];
  let hoveredHotspot = null;

  // Camera targets for smooth lerp
  const targetCamPos = new THREE.Vector3(0, 0, 85);
  const targetLookAt = new THREE.Vector3(0, 0, 0);
  const currentLookAt = new THREE.Vector3(0, 0, 0);

  // Palette definitions
  const PALETTES = {
    arc: {
      primary: 0x00f0ff,
      secondary: 0x0284c7,
      core: 0x38bdf8,
      glow: 0x0ea5e9,
      accent: 0xa5f3fc,
      ground: 0x031728,
    },
    stark: {
      primary: 0xff3b30,
      secondary: 0xffcc00,
      core: 0xff9500,
      glow: 0xff2d55,
      accent: 0xffe600,
      ground: 0x240508,
    },
  };

  function getPalette() {
    return isStarkMode ? PALETTES.stark : PALETTES.arc;
  }

  // Initialize Scene
  function init() {
    canvasContainer = document.getElementById('threejs-container');
    canvas = document.getElementById('threejs-canvas');
    if (!canvasContainer || !canvas) return;

    const width = canvasContainer.clientWidth || window.innerWidth;
    const height = canvasContainer.clientHeight || window.innerHeight;

    // Scene & Fog
    scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x060b14, 0.0035);

    // Camera
    camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 1000);
    camera.position.set(0, 15, 85);
    targetCamPos.copy(camera.position);

    // Renderer
    renderer = new THREE.WebGLRenderer({
      canvas: canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;

    // WebGL Context Lost handling
    canvas.addEventListener('webglcontextlost', (e) => {
      e.preventDefault();
      console.warn('WebGL context lost. Pausing 3D spatial loop.');
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
    });
    canvas.addEventListener('webglcontextrestored', () => {
      console.info('WebGL context restored. Rebuilding 3D scene.');
      init();
    });

    // Raycaster & Mouse
    raycaster = new THREE.Raycaster();
    mouse = new THREE.Vector2(-999, -999);

    // Lighting
    setupLighting();

    // Main rotating group
    mainGroup = new THREE.Group();
    scene.add(mainGroup);

    // Build modules
    buildBackgroundGrid();
    buildParticleField();
    buildArcReactor();
    buildGlobalGlobe();
    buildArmorMatrix();

    // Set initial mode
    setMode('reactor');

    // Controls & Events
    setupOrbitInteraction();
    window.addEventListener('resize', onWindowResize);

    // Start render loop
    animate(0);
  }

  function setupLighting() {
    const ambient = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambient);

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.4);
    keyLight.position.set(40, 60, 50);
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0x00f0ff, 1.8);
    rimLight.position.set(-50, -30, -50);
    scene.add(rimLight);

    const pointLight = new THREE.PointLight(0x00f0ff, 3, 70);
    pointLight.position.set(0, 0, 0);
    pointLight.name = 'coreLight';
    scene.add(pointLight);
  }

  // ── Background Space Grid & Ambient Particles ───────────────────────────

  function buildBackgroundGrid() {
    const size = 200;
    const divisions = 30;
    const grid = new THREE.GridHelper(size, divisions, 0x1e3a5f, 0x09192b);
    grid.position.y = -35;
    scene.add(grid);

    // Outer cyber ring
    const ringGeo = new THREE.RingGeometry(80, 81, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x0ea5e9,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.15,
    });
    const horizonRing = new THREE.Mesh(ringGeo, ringMat);
    horizonRing.rotation.x = Math.PI / 2;
    horizonRing.position.y = -34.8;
    scene.add(horizonRing);
  }

  function buildParticleField() {
    const pCount = 1200;
    particleGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(pCount * 3);
    const velocities = new Float32Array(pCount * 3);
    const scales = new Float32Array(pCount);

    for (let i = 0; i < pCount; i++) {
      const radius = 25 + Math.random() * 45;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = radius * Math.cos(phi);

      velocities[i * 3] = (Math.random() - 0.5) * 0.05;
      velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.05;
      velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.05;

      scales[i] = Math.random() * 2 + 1;
    }

    particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    particleGeo.setAttribute('scale', new THREE.BufferAttribute(scales, 1));

    const pMat = new THREE.PointsMaterial({
      color: 0x38bdf8,
      size: 1.2,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending,
    });

    particleSystem = new THREE.Points(particleGeo, pMat);
    scene.add(particleSystem);
  }

  // ── Mode 1: Arc Reactor Hologram ────────────────────────────────────────

  function buildArcReactor() {
    reactorGroup = new THREE.Group();
    reactorGroup.name = 'reactorGroup';

    const p = getPalette();

    // 1. Central Plasma Core Sphere
    const coreGeo = new THREE.SphereGeometry(6.5, 32, 32);
    const coreMat = new THREE.MeshStandardMaterial({
      color: p.core,
      emissive: p.core,
      emissiveIntensity: 1.5,
      roughness: 0.2,
      metalness: 0.8,
      wireframe: false,
    });
    const core = new THREE.Mesh(coreGeo, coreMat);
    core.name = 'plasmaCore';
    reactorGroup.add(core);

    // Inner wireframe shell
    const innerWireGeo = new THREE.IcosahedronGeometry(7.2, 2);
    const innerWireMat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      wireframe: true,
      transparent: true,
      opacity: 0.45,
    });
    const innerWire = new THREE.Mesh(innerWireGeo, innerWireMat);
    innerWire.name = 'innerWire';
    reactorGroup.add(innerWire);

    // 2. Primary Torus Confinement Coil
    const torusGeo = new THREE.TorusGeometry(14, 1.8, 16, 64);
    const torusMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.3,
      metalness: 0.9,
    });
    const torus = new THREE.Mesh(torusGeo, torusMat);
    reactorGroup.add(torus);

    // Glowing emitter strip inside torus
    const stripGeo = new THREE.TorusGeometry(14, 0.4, 16, 64);
    const stripMat = new THREE.MeshBasicMaterial({
      color: p.primary,
      transparent: true,
      opacity: 0.85,
    });
    const emitterStrip = new THREE.Mesh(stripGeo, stripMat);
    emitterStrip.name = 'emitterStrip';
    reactorGroup.add(emitterStrip);

    // 3. Ten Radial Magnetic Energy Segments
    const segCount = 10;
    const segmentGroup = new THREE.Group();
    segmentGroup.name = 'reactorSegments';

    for (let i = 0; i < segCount; i++) {
      const angle = (i / segCount) * Math.PI * 2;
      const segGeo = new THREE.BoxGeometry(2.4, 5.5, 3.2);
      const segMat = new THREE.MeshStandardMaterial({
        color: 0x0f172a,
        metalness: 0.95,
        roughness: 0.2,
      });
      const segment = new THREE.Mesh(segGeo, segMat);
      segment.position.set(Math.cos(angle) * 14, Math.sin(angle) * 14, 0);
      segment.rotation.z = angle + Math.PI / 2;

      // Copper wound wire coil
      const coilGeo = new THREE.CylinderGeometry(0.8, 0.8, 4, 12);
      const coilMat = new THREE.MeshStandardMaterial({
        color: 0xd97706,
        metalness: 0.8,
        roughness: 0.3,
      });
      const coil = new THREE.Mesh(coilGeo, coilMat);
      coil.rotation.z = Math.PI / 2;
      segment.add(coil);

      segmentGroup.add(segment);
    }
    reactorGroup.add(segmentGroup);

    // 4. Outer Rotating Gimbal Rings
    const gimbal1Geo = new THREE.TorusGeometry(20, 0.6, 12, 64);
    const gimbal1Mat = new THREE.MeshBasicMaterial({
      color: p.primary,
      wireframe: true,
      transparent: true,
      opacity: 0.6,
    });
    const gimbal1 = new THREE.Mesh(gimbal1Geo, gimbal1Mat);
    gimbal1.name = 'gimbal1';
    reactorGroup.add(gimbal1);

    const gimbal2Geo = new THREE.TorusGeometry(23.5, 0.5, 12, 64);
    const gimbal2Mat = new THREE.MeshBasicMaterial({
      color: p.secondary,
      wireframe: true,
      transparent: true,
      opacity: 0.5,
    });
    const gimbal2 = new THREE.Mesh(gimbal2Geo, gimbal2Mat);
    gimbal2.name = 'gimbal2';
    gimbal2.rotation.x = Math.PI / 4;
    reactorGroup.add(gimbal2);

    const gimbal3Geo = new THREE.TorusGeometry(27, 0.4, 12, 64);
    const gimbal3Mat = new THREE.MeshBasicMaterial({
      color: p.accent,
      transparent: true,
      opacity: 0.3,
    });
    const gimbal3 = new THREE.Mesh(gimbal3Geo, gimbal3Mat);
    gimbal3.name = 'gimbal3';
    gimbal3.rotation.y = Math.PI / 3;
    reactorGroup.add(gimbal3);

    // 5. Interactive Sensor Hotspots
    createHotspot('Core Plasma Torus', '98.7% Quantum Density · 4.8 GW Output', 0, 0, 7.5, reactorGroup);
    createHotspot('Magnetic Containment Coil', 'Flux: 14.2 Tesla · Superconducting at 4.2 K', 14, 0, 3, reactorGroup);
    createHotspot('Outer Inertial Gimbal', 'Rotation: 1,840 RPM · Gyro Synchronized', -20, 0, 0, reactorGroup);
    createHotspot('Sub-Harmonic Exciter', 'Phase Alignment: 99.4% · Zero Harmonic Leak', 0, -23.5, 0, reactorGroup);

    mainGroup.add(reactorGroup);
  }

  // ── Mode 2: Global Orbital Telemetry Globe ───────────────────────────────

  function buildGlobalGlobe() {
    globeGroup = new THREE.Group();
    globeGroup.name = 'globeGroup';
    globeGroup.visible = false;

    const p = getPalette();

    // 1. Earth wireframe sphere
    const globeGeo = new THREE.SphereGeometry(18, 36, 36);
    const globeMat = new THREE.MeshBasicMaterial({
      color: p.secondary,
      wireframe: true,
      transparent: true,
      opacity: 0.35,
    });
    const globeMesh = new THREE.Mesh(globeGeo, globeMat);
    globeGroup.add(globeMesh);

    // Inner dark sphere to occlude back
    const innerGlobe = new THREE.Mesh(
      new THREE.SphereGeometry(17.6, 32, 32),
      new THREE.MeshBasicMaterial({ color: 0x050d18 })
    );
    globeGroup.add(innerGlobe);

    // 2. Continental coordinate beacons
    const locations = [
      { name: 'Stark Tower (New York)', lat: 40.71, lon: -74.0, desc: 'Primary Intelligence Hub · 10 Gbps Uplink' },
      { name: 'Malibu Lab (California)', lat: 34.02, lon: -118.77, desc: 'R&D Fabrication · Nanotech Foundry' },
      { name: 'London Operations Hub', lat: 51.5, lon: -0.12, desc: 'European Gateway · Secure Relay' },
      { name: 'Tokyo Research Center', lat: 35.67, lon: 139.65, desc: 'Quantum Neural Node · Latency 14ms' },
      { name: 'Zurich Secure Vault', lat: 47.37, lon: 8.54, desc: 'Encrypted Cold Storage · Zero-Knowledge' },
      { name: 'Sydney Sensor Array', lat: -33.86, lon: 151.2, desc: 'Southern Hemisphere Telemetry Station' },
    ];

    locations.forEach((loc) => {
      const phi = (90 - loc.lat) * (Math.PI / 180);
      const theta = (loc.lon + 180) * (Math.PI / 180);
      const radius = 18.2;

      const x = -(radius * Math.sin(phi) * Math.cos(theta));
      const z = radius * Math.sin(phi) * Math.sin(theta);
      const y = radius * Math.cos(phi);

      // Beacon pin
      const pinGeo = new THREE.CylinderGeometry(0.3, 0.1, 3.5, 8);
      const pinMat = new THREE.MeshBasicMaterial({ color: p.primary });
      const pin = new THREE.Mesh(pinGeo, pinMat);
      pin.position.set(x, y, z);
      pin.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(x, y, z).normalize());
      globeGroup.add(pin);

      createHotspot(loc.name, loc.desc, x * 1.05, y * 1.05, z * 1.05, globeGroup);
    });

    // 3. Orbital Satellite Rings with Moving Satellites
    const orbit1 = new THREE.Mesh(
      new THREE.TorusGeometry(26, 0.15, 8, 80),
      new THREE.MeshBasicMaterial({ color: p.primary, transparent: true, opacity: 0.5 })
    );
    orbit1.rotation.x = Math.PI / 3;
    globeGroup.add(orbit1);

    const orbit2 = new THREE.Mesh(
      new THREE.TorusGeometry(30, 0.15, 8, 80),
      new THREE.MeshBasicMaterial({ color: p.accent, transparent: true, opacity: 0.4 })
    );
    orbit2.rotation.y = Math.PI / 2.5;
    orbit2.rotation.x = -Math.PI / 6;
    globeGroup.add(orbit2);

    // Satellites
    const satGeo = new THREE.BoxGeometry(1.2, 0.6, 2.0);
    const satMat = new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.9, roughness: 0.1 });
    const sat1 = new THREE.Mesh(satGeo, satMat);
    sat1.position.set(26, 0, 0);
    orbit1.add(sat1);

    const sat2 = new THREE.Mesh(satGeo, satMat);
    sat2.position.set(30, 0, 0);
    orbit2.add(sat2);

    mainGroup.add(globeGroup);
  }

  // ── Mode 3: Mark L Holographic Armor Matrix ──────────────────────────────

  function buildArmorMatrix() {
    armorGroup = new THREE.Group();
    armorGroup.name = 'armorGroup';
    armorGroup.visible = false;

    const p = getPalette();

    // Layer 1: Core Neural Spine Column (Inner)
    const spineGeo = new THREE.CylinderGeometry(1.8, 2.2, 28, 16);
    const spineMat = new THREE.MeshStandardMaterial({
      color: 0x334155,
      metalness: 0.9,
      roughness: 0.2,
    });
    const spine = new THREE.Mesh(spineGeo, spineMat);
    spine.name = 'armorSpine';
    armorGroup.add(spine);

    // Layer 2: Thoracic Hydraulic Ribcage (Middle)
    const ribGroup = new THREE.Group();
    ribGroup.name = 'armorRibs';
    for (let i = -3; i <= 3; i++) {
      const ribGeo = new THREE.TorusGeometry(7.5 + Math.abs(i) * 0.4, 0.6, 8, 24, Math.PI * 1.3);
      const ribMat = new THREE.MeshStandardMaterial({
        color: p.secondary,
        metalness: 0.8,
        roughness: 0.3,
        wireframe: true,
      });
      const rib = new THREE.Mesh(ribGeo, ribMat);
      rib.position.y = i * 3.2;
      rib.rotation.x = Math.PI / 2;
      rib.rotation.z = -Math.PI * 0.15;
      ribGroup.add(rib);
    }
    armorGroup.add(ribGroup);

    // Layer 3: Chest Repulsor Receptacle
    const chestCoreGeo = new THREE.CylinderGeometry(3.5, 3.5, 2.5, 6);
    const chestCoreMat = new THREE.MeshStandardMaterial({
      color: p.core,
      emissive: p.core,
      emissiveIntensity: 1.6,
      metalness: 0.8,
    });
    const chestCore = new THREE.Mesh(chestCoreGeo, chestCoreMat);
    chestCore.rotation.x = Math.PI / 2;
    chestCore.position.set(0, 4, 8);
    chestCore.name = 'armorChestCore';
    armorGroup.add(chestCore);

    // Layer 4: Explodable Nanotech Armor Plates (Outer)
    const platesGroup = new THREE.Group();
    platesGroup.name = 'armorPlates';

    // Left and Right Pectoral Plates
    const pecGeo = new THREE.BoxGeometry(6.5, 7.5, 1.8);
    const plateMat = new THREE.MeshStandardMaterial({
      color: isStarkMode ? 0xb91c1c : 0x0284c7,
      metalness: 0.85,
      roughness: 0.25,
    });

    const leftPec = new THREE.Mesh(pecGeo, plateMat.clone());
    leftPec.position.set(-5.5, 5, 8.5);
    leftPec.userData = { normal: new THREE.Vector3(-1, 0.2, 1).normalize() };
    platesGroup.add(leftPec);

    const rightPec = new THREE.Mesh(pecGeo, plateMat.clone());
    rightPec.position.set(5.5, 5, 8.5);
    rightPec.userData = { normal: new THREE.Vector3(1, 0.2, 1).normalize() };
    platesGroup.add(rightPec);

    // Shoulder Pauldrons
    const shoulderGeo = new THREE.ConeGeometry(5.5, 6, 4);
    const leftShoulder = new THREE.Mesh(shoulderGeo, plateMat.clone());
    leftShoulder.position.set(-13, 11, 2);
    leftShoulder.rotation.z = Math.PI / 4;
    leftShoulder.userData = { normal: new THREE.Vector3(-1.2, 0.8, 0.3).normalize() };
    platesGroup.add(leftShoulder);

    const rightShoulder = new THREE.Mesh(shoulderGeo, plateMat.clone());
    rightShoulder.position.set(13, 11, 2);
    rightShoulder.rotation.z = -Math.PI / 4;
    rightShoulder.userData = { normal: new THREE.Vector3(1.2, 0.8, 0.3).normalize() };
    platesGroup.add(rightShoulder);

    // Abdominal Plating
    for (let r = 0; r < 3; r++) {
      const abGeo = new THREE.BoxGeometry(9 - r * 1.5, 2.2, 1.6);
      const abPlate = new THREE.Mesh(abGeo, plateMat.clone());
      abPlate.position.set(0, -1 - r * 2.8, 7.5 - r * 0.4);
      abPlate.userData = { normal: new THREE.Vector3(0, -0.2 - r * 0.1, 1).normalize() };
      platesGroup.add(abPlate);
    }

    armorGroup.add(platesGroup);

    createHotspot('Mark L Nanotech Armor', 'Gold-Titanium Alloy · Self-Healing Matrix', 0, 4, 11, armorGroup);
    createHotspot('Hydraulic Biomechanical Ribs', 'Tensile Strength: 42,000 MPa · G-Force Dampened', -9, -2, 4, armorGroup);
    createHotspot('Neural Fiber Spine', 'Optic Bus: 120 Tbps · Nanosecond Synaptic Response', 0, 12, -2, armorGroup);

    mainGroup.add(armorGroup);
  }

  // ── Hotspot Helper ───────────────────────────────────────────────────────

  function createHotspot(title, description, x, y, z, parentGroup) {
    const p = getPalette();
    const group = new THREE.Group();
    group.position.set(x, y, z);

    // Pulsing inner ring
    const ringGeo = new THREE.RingGeometry(0.8, 1.1, 16);
    const ringMat = new THREE.MeshBasicMaterial({
      color: p.primary,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.85,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    group.add(ring);

    // Center dot
    const dotGeo = new THREE.CircleGeometry(0.4, 12);
    const dotMat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      side: THREE.DoubleSide,
    });
    const dot = new THREE.Mesh(dotGeo, dotMat);
    group.add(dot);

    group.userData = {
      isHotspot: true,
      title: title,
      description: description,
      baseScale: 1,
    };

    parentGroup.add(group);
    hotspots.push(group);
  }

  // ── Orbit & Interaction Controls ─────────────────────────────────────────

  function setupOrbitInteraction() {
    let isDragging = false;
    let prevMouseX = 0;
    let prevMouseY = 0;
    let rotVelX = 0;
    let rotVelY = 0;

    canvas.addEventListener('mousedown', (e) => {
      isDragging = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    });

    window.addEventListener('mouseup', () => {
      isDragging = false;
    });

    window.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      if (isDragging && mainGroup) {
        const deltaX = e.clientX - prevMouseX;
        const deltaY = e.clientY - prevMouseY;
        prevMouseX = e.clientX;
        prevMouseY = e.clientY;

        rotVelY = deltaX * 0.005;
        rotVelX = deltaY * 0.005;

        mainGroup.rotation.y += rotVelY;
        mainGroup.rotation.x += rotVelX;
      }
    });

    // Touch support for mobile devices
    canvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        isDragging = true;
        prevMouseX = e.touches[0].clientX;
        prevMouseY = e.touches[0].clientY;
      }
    }, { passive: true });

    window.addEventListener('touchend', () => {
      isDragging = false;
    });

    window.addEventListener('touchmove', (e) => {
      if (isDragging && e.touches.length === 1 && mainGroup) {
        const deltaX = e.touches[0].clientX - prevMouseX;
        const deltaY = e.touches[0].clientY - prevMouseY;
        prevMouseX = e.touches[0].clientX;
        prevMouseY = e.touches[0].clientY;

        mainGroup.rotation.y += deltaX * 0.006;
        mainGroup.rotation.x += deltaY * 0.006;
      }
    }, { passive: true });

    // Zoom on wheel
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY * 0.05;
      targetCamPos.z = Math.max(35, Math.min(140, targetCamPos.z + zoomFactor));
    }, { passive: false });

    // Click hotspot to show diagnostic inspect card
    canvas.addEventListener('click', () => {
      if (hoveredHotspot) {
        showHotspotCard(hoveredHotspot.userData.title, hoveredHotspot.userData.description);
        // Smoothly focus camera towards hotspot
        targetLookAt.copy(hoveredHotspot.position);
      }
    });
  }

  function showHotspotCard(title, description) {
    const card = document.getElementById('hotspot-inspect-card');
    const titleEl = document.getElementById('hotspot-title');
    const descEl = document.getElementById('hotspot-desc');
    if (!card || !titleEl || !descEl) return;

    titleEl.textContent = title;
    descEl.textContent = description;
    card.classList.add('visible');

    // Auto-dismiss after 6 seconds or on manual close
    clearTimeout(card._timer);
    card._timer = setTimeout(() => {
      card.classList.remove('visible');
    }, 6000);
  }

  // ── Public API Methods (Exported to window) ──────────────────────────────

  function setMode(mode) {
    currentMode = mode;
    if (reactorGroup) reactorGroup.visible = mode === 'reactor';
    if (globeGroup) globeGroup.visible = mode === 'globe';
    if (armorGroup) armorGroup.visible = mode === 'armor';

    // Set camera distances appropriate for module
    if (mode === 'reactor') {
      targetCamPos.set(0, 10, 80);
    } else if (mode === 'globe') {
      targetCamPos.set(0, 15, 95);
    } else if (mode === 'armor') {
      targetCamPos.set(0, 8, 75);
    }
    targetLookAt.set(0, 0, 0);

    // Update UI buttons
    document.querySelectorAll('.mode-3d-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    const explodeSlider = document.getElementById('explodeSliderContainer');
    if (explodeSlider) {
      explodeSlider.style.display = mode === 'armor' ? 'flex' : 'none';
    }
  }

  function setCameraPreset(preset) {
    if (preset === 'front') {
      targetCamPos.set(0, 2, 75);
      if (mainGroup) {
        mainGroup.rotation.x = 0;
        mainGroup.rotation.y = 0;
      }
    } else if (preset === 'iso') {
      targetCamPos.set(45, 35, 65);
    } else if (preset === 'top') {
      targetCamPos.set(0, 85, 5);
      if (mainGroup) {
        mainGroup.rotation.x = 0;
      }
    } else if (preset === 'orbit') {
      autoRotate = !autoRotate;
    }
    targetLookAt.set(0, 0, 0);
  }

  function setStarkTheme(enabled) {
    isStarkMode = enabled;
    const p = getPalette();

    // Update point light
    const coreLight = scene ? scene.getObjectByName('coreLight') : null;
    if (coreLight) {
      coreLight.color.setHex(p.primary);
    }

    // Update reactor materials
    if (reactorGroup) {
      const core = reactorGroup.getObjectByName('plasmaCore');
      if (core) {
        core.material.color.setHex(p.core);
        core.material.emissive.setHex(p.core);
      }
      const strip = reactorGroup.getObjectByName('emitterStrip');
      if (strip) strip.material.color.setHex(p.primary);
      const gimbal1 = reactorGroup.getObjectByName('gimbal1');
      if (gimbal1) gimbal1.material.color.setHex(p.primary);
    }

    // Update armor materials
    if (armorGroup) {
      const platesGroup = armorGroup.getObjectByName('armorPlates');
      if (platesGroup) {
        platesGroup.children.forEach((mesh) => {
          if (mesh.material) {
            mesh.material.color.setHex(isStarkMode ? 0xb91c1c : 0x0284c7);
          }
        });
      }
    }

    // Update particle color
    if (particleSystem) {
      particleSystem.material.color.setHex(p.primary);
    }
  }

  function setExplodeAmount(amount) {
    explodeAmount = amount;
    if (!armorGroup) return;

    const platesGroup = armorGroup.getObjectByName('armorPlates');
    if (!platesGroup) return;

    platesGroup.children.forEach((mesh) => {
      const norm = mesh.userData?.normal;
      if (norm) {
        mesh.position.x = mesh.position.x + norm.x * (amount * 18 - (mesh.userData._lastExplode || 0));
        mesh.position.y = mesh.position.y + norm.y * (amount * 18 - (mesh.userData._lastExplode || 0));
        mesh.position.z = mesh.position.z + norm.z * (amount * 18 - (mesh.userData._lastExplode || 0));
        mesh.userData._lastExplode = amount * 18;
      }
    });
  }

  function setAudioReactive(active, intensity) {
    isSpeaking = active;
    audioPulse = intensity || (active ? 1.0 : 0);
  }

  // ── Render Loop ──────────────────────────────────────────────────────────

  function animate(time) {
    animationFrameId = requestAnimationFrame(animate);

    const t = time * 0.001;

    // Smooth camera lerp
    camera.position.lerp(targetCamPos, 0.05);
    currentLookAt.lerp(targetLookAt, 0.05);
    camera.lookAt(currentLookAt);

    // Audio reactivity decay / pulsation
    if (isSpeaking) {
      audioPulse = 0.5 + Math.sin(t * 12) * 0.5;
    } else {
      audioPulse = Math.max(0, audioPulse - 0.02);
    }

    // Auto-rotate main scene if enabled
    if (autoRotate && mainGroup) {
      const speedMultiplier = 1.0 + audioPulse * 1.5;
      mainGroup.rotation.y += rotateSpeed * speedMultiplier;
    }

    // Animate Module 1: Reactor Core
    if (reactorGroup && reactorGroup.visible) {
      const core = reactorGroup.getObjectByName('plasmaCore');
      if (core) {
        const pulse = 1.0 + Math.sin(t * 4) * 0.06 + audioPulse * 0.2;
        core.scale.set(pulse, pulse, pulse);
        core.material.emissiveIntensity = 1.5 + audioPulse * 2.0;
      }

      const innerWire = reactorGroup.getObjectByName('innerWire');
      if (innerWire) {
        innerWire.rotation.x = t * 0.8;
        innerWire.rotation.y = -t * 1.2;
      }

      const gimbal1 = reactorGroup.getObjectByName('gimbal1');
      if (gimbal1) gimbal1.rotation.z = -t * 0.4;

      const gimbal2 = reactorGroup.getObjectByName('gimbal2');
      if (gimbal2) gimbal2.rotation.x = t * 0.5;

      const gimbal3 = reactorGroup.getObjectByName('gimbal3');
      if (gimbal3) gimbal3.rotation.y = -t * 0.6;
    }

    // Animate Module 2: Global Globe
    if (globeGroup && globeGroup.visible) {
      globeGroup.rotation.y += 0.003;
    }

    // Animate Particles
    if (particleGeo) {
      const positions = particleGeo.attributes.position.array;
      const count = positions.length / 3;
      for (let i = 0; i < count; i++) {
        positions[i * 3 + 1] += Math.sin(t + i) * 0.02;
      }
      particleGeo.attributes.position.needsUpdate = true;
    }

    // Orient Hotspots to face Camera
    hotspots.forEach((h) => {
      h.quaternion.copy(camera.quaternion);
      // Pulsing scale
      const s = 1.0 + Math.sin(t * 3 + h.position.x) * 0.15;
      h.scale.set(s, s, s);
    });

    // Raycast hover detection on hotspots
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(hotspots, true);

    if (intersects.length > 0) {
      let root = intersects[0].object;
      while (root.parent && !root.userData?.isHotspot) {
        root = root.parent;
      }
      if (root.userData?.isHotspot) {
        hoveredHotspot = root;
        canvas.style.cursor = 'pointer';
        const tooltip = document.getElementById('hotspot-tooltip');
        if (tooltip) {
          tooltip.textContent = root.userData.title;
          tooltip.style.display = 'block';
          const p2d = toScreenPosition(root, camera, renderer);
          tooltip.style.left = p2d.x + 'px';
          tooltip.style.top = p2d.y - 30 + 'px';
        }
      }
    } else {
      hoveredHotspot = null;
      canvas.style.cursor = 'default';
      const tooltip = document.getElementById('hotspot-tooltip');
      if (tooltip) tooltip.style.display = 'none';
    }

    renderer.render(scene, camera);
  }

  function toScreenPosition(obj, cam, rend) {
    const vector = new THREE.Vector3();
    obj.getWorldPosition(vector);
    vector.project(cam);
    const widthHalf = rend.domElement.clientWidth / 2;
    const heightHalf = rend.domElement.clientHeight / 2;
    return {
      x: vector.x * widthHalf + widthHalf,
      y: -(vector.y * heightHalf) + heightHalf,
    };
  }

  function onWindowResize() {
    if (!camera || !renderer || !canvasContainer) return;
    const width = canvasContainer.clientWidth || window.innerWidth;
    const height = canvasContainer.clientHeight || window.innerHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  }

  // ── Attach Public Controls to window.friday3D ────────────────────────────
  window.friday3D = {
    init: init,
    setMode: setMode,
    setCameraPreset: setCameraPreset,
    setStarkTheme: setStarkTheme,
    setExplodeAmount: setExplodeAmount,
    setAudioReactive: setAudioReactive,
    toggleAutoRotate: () => {
      autoRotate = !autoRotate;
      return autoRotate;
    },
  };

  // Auto-init on DOMContentLoaded or immediate
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
