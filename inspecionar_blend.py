import bpy
print("BLENDER", bpy.app.version_string)
for c in bpy.data.collections: print("COL", c.name, len(c.objects))
for o in bpy.data.objects: print("OBJ", o.name, o.type, tuple(round(v,3) for v in o.dimensions))
