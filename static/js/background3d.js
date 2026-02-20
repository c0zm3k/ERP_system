// 3D Background Animation using Three.js
let scene, camera, renderer, particles;

function init3D() {
    const container = document.getElementById('canvas-container');
    if (!container) return;

    // Setup
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });

    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0); // Transparent background
    document.getElementById('canvas-container').appendChild(renderer.domElement);

    // Objects
    const geometry = new THREE.BufferGeometry();
    const vertices = [];
    const size = 1500;
    const pointsCount = 600;

    for (let i = 0; i < pointsCount; i++) {
        vertices.push(
            (Math.random() - 0.5) * size,
            (Math.random() - 0.5) * size,
            (Math.random() - 0.5) * size
        );
    }

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));

    // Material - Professional Light Blue
    const material = new THREE.PointsMaterial({
        color: 0x2563eb,
        size: 2.5,
        transparent: true,
        opacity: 0.25,
        sizeAttenuation: true
    });

    const points = new THREE.Points(geometry, material);
    scene.add(points);

    // Subtle Moving Lines (Geometric feel)
    const lineMaterial = new THREE.LineBasicMaterial({ color: 0x2563eb, transparent: true, opacity: 0.1 });
    const lines = [];

    for (let i = 0; i < 40; i++) {
        const lineGeo = new THREE.BufferGeometry();
        const p1 = new THREE.Vector3((Math.random() - 0.5) * size, (Math.random() - 0.5) * size, (Math.random() - 0.5) * size);
        const p2 = new THREE.Vector3((Math.random() - 0.5) * size, (Math.random() - 0.5) * size, (Math.random() - 0.5) * size);
        lineGeo.setFromPoints([p1, p2]);
        const line = new THREE.Line(lineGeo, lineMaterial);
        scene.add(line);
        lines.push({ mesh: line, p1, p2, offset: Math.random() * Math.PI });
    }

    camera.position.z = 400;

    // Animation
    function animate() {
        requestAnimationFrame(animate);

        points.rotation.y += 0.0003;
        points.rotation.x += 0.0001;

        lines.forEach(l => {
            l.mesh.rotation.y += 0.0005;
            l.mesh.rotation.z += 0.0002;
        });

        renderer.render(scene, camera);
    }

    // Resize
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    animate();
}

document.addEventListener('DOMContentLoaded', init3D);
