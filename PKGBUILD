# Maintainer: Philotes Team <zntrx@archlinux>
pkgname=philotes
pkgver=2.0.3
pkgrel=1
pkgdesc="Linux-first communication application container designed to run continuously on Arch Linux"
arch=('any')
url="https://github.com/philotes/philotes"
license=('MIT')
depends=('python' 'python-gobject' 'webkitgtk-6.0' 'gtk4' 'hicolor-icon-theme')
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=()

build() {
    cd "${startdir}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${startdir}"
    python -m installer --prefix=/opt/philotes --destdir="${pkgdir}" dist/*.whl

    # Symlink executables to /usr/bin for system PATH access
    install -dm755 "${pkgdir}/usr/bin"
    ln -s /opt/philotes/bin/philotes "${pkgdir}/usr/bin/philotes"
    ln -s /opt/philotes/bin/philo-chat "${pkgdir}/usr/bin/philo-chat"
    ln -s /opt/philotes/bin/philo-msgs "${pkgdir}/usr/bin/philo-msgs"

    # Register /opt/philotes site-packages path in system Python
    _pyver=$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    install -dm755 "${pkgdir}/usr/lib/python${_pyver}/site-packages"
    echo "/opt/philotes/lib/python${_pyver}/site-packages" > "${pkgdir}/usr/lib/python${_pyver}/site-packages/philotes.pth"

    # Desktop Launcher
    install -Dm644 philotes.desktop "${pkgdir}/usr/share/applications/philotes.desktop"

    # Icons (System & /opt/philotes)
    install -Dm644 icons/hicolor/philotes.svg "${pkgdir}/usr/share/icons/hicolor/scalable/apps/philotes.svg"
    install -Dm644 icons/hicolor/philotes.svg "${pkgdir}/opt/philotes/icons/hicolor/philotes.svg"
    install -Dm644 icons/greyscale/philotes.svg "${pkgdir}/opt/philotes/icons/greyscale/philotes.svg"
    install -Dm644 icons/hicolor/chat.svg "${pkgdir}/opt/philotes/icons/hicolor/chat.svg"
    install -Dm644 icons/greyscale/chat.svg "${pkgdir}/opt/philotes/icons/greyscale/chat.svg"
    install -Dm644 icons/hicolor/messages.svg "${pkgdir}/opt/philotes/icons/hicolor/messages.svg"
    install -Dm644 icons/greyscale/messages.svg "${pkgdir}/opt/philotes/icons/greyscale/messages.svg"

    # Stylesheet Themes
    install -Dm644 styles/dark-sharp.css "${pkgdir}/opt/philotes/styles/dark-sharp.css"

    # Cleanup temporary python build directories
    rm -rf "${startdir}/build" "${startdir}/dist" "${startdir}"/*.egg-info
}
