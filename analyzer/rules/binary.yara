rule MachO {
    condition:
        uint32(0) == 0xfeedface or uint32(0) == 0xcefaedfe or uint32(0) == 0xfeedfacf or uint32(0) == 0xcffaedfe or uint32(0) == 0xcafebabe or uint32(0) == 0xbebafeca
}

rule PE {
	strings:
		$mz = "MZ"
	condition:
		$mz at 0 and uint32(uint32(0x3C)) == 0x4550
}

rule ELF {
    strings:

    condition:
}
