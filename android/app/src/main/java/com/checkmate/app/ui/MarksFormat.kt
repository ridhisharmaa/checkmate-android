package com.checkmate.app.ui

/** Shows whole marks without a trailing ".0" (11.0 -> "11"); keeps other values as they are. */
fun Double.marks(): String = if (this % 1.0 == 0.0) this.toLong().toString() else this.toString()
