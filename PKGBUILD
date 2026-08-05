# Maintainer: Philotes Team <zntrx@archlinux>
pkgname=philotes
pkgver=2.0.2
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
    python -m installer --destdir="${pkgdir}" dist/*.whl

    # Desktop Launcher
    install -Dm644 philotes.desktop "${pkgdir}/usr/share/applications/philotes.desktop"

    # Icons
    install -Dm644 icons/hicolor/philotes.svg "${pkgdir}/usr/share/icons/hicolor/scalable/apps/philotes.svg"
    install -Dm644 icons/hicolor/philotes.svg "${pkgdir}/usr/share/philotes/icons/hicolor/philotes.svg"
    install -Dm644 icons/greyscale/philotes.svg "${pkgdir}/usr/share/philotes/icons/greyscale/philotes.svg"
    install -Dm644 icons/hicolor/chat.svg "${pkgdir}/usr/share/philotes/icons/hicolor/chat.svg"
    install -Dm644 icons/greyscale/chat.svg "${pkgdir}/usr/share/philotes/icons/greyscale/chat.svg"
    install -Dm644 icons/hicolor/messages.svg "${pkgdir}/usr/share/philotes/icons/hicolor/messages.svg"
    install -Dm644 icons/greyscale/messages.svg "${pkgdir}/usr/share/philotes/icons/greyscale/messages.svg"

    # Stylesheet Themes
    install -Dm644 styles/dark-sharp.css "${pkgdir}/usr/share/philotes/styles/dark-sharp.css"
}
