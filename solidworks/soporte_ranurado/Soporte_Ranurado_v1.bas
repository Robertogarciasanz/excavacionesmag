Attribute VB_Name = "SoporteRanurado_v1"
' =====================================================================
'  SOPORTE CON RANURA EN ARCO  -  macro de modelado parametrico
'  SolidWorks 2020+ (VBA).  Plano: Soporte_Ranurado_plano.pdf (SR-001)
'
'  Ejes: X largo (0..160), Y alto (0 = cara de apoyo), Z fondo
'        (Z = 0 cara posterior del alma; los bujes salen hacia +Z).
'  Todas las cotas son variables globales: Herramientas > Ecuaciones.
'
'  Arbol: Base > Alma > Oreja > Bujes > Taladros_Bujes > Ranura >
'         Taladros_Base > Avellanados > Redondeo_Base
' =====================================================================
Option Explicit

Const PI As Double = 3.14159265358979

' ---- Cotas (mm) ----
Const vL As Double = 160      ' largo de la base
Const vH As Double = 13       ' alto de la base
Const vD As Double = 54       ' fondo de la base
Const vE As Double = 20       ' espesor del alma y la oreja
Const vXP As Double = 48      ' X del eje del buje inferior (pivote)
Const vYP As Double = 46      ' Y del eje del buje inferior
Const vRR As Double = 40      ' radio de la ranura = distancia entre bujes
Const vDB As Double = 33      ' diametro exterior de los bujes
Const vLB As Double = 44      ' largo de los bujes
Const vDS As Double = 17      ' taladro buje inferior
Const vDT As Double = 12      ' taladro buje superior
Const vAR As Double = 24      ' ancho de la oreja (R28..R52)
Const vAS As Double = 12      ' ancho de la ranura (R34..R46)
Const vXO As Double = 87      ' X del extremo de la oreja (48 + 39)
Const vS1 As Double = 18      ' angulo inicial de la ranura (grados)
Const vS2 As Double = 52      ' angulo final de la ranura (grados)
Const vXG As Double = 110     ' pie del nervio inclinado
Const vXB1 As Double = 100    ' X taladro avellanado 1
Const vXB2 As Double = 135    ' X taladro avellanado 2
Const vZB As Double = 34      ' Z de los taladros avellanados
Const vDA As Double = 14      ' taladro de la base
Const vDAV As Double = 28     ' diametro del avellanado a 90 grados
Const vRF As Double = 10      ' redondeo esquinas delanteras de la base

Dim swApp As SldWorks.SldWorks
Dim Part As SldWorks.ModelDoc2
Dim eqMgr As SldWorks.EquationMgr
Dim mUtil As SldWorks.MathUtility
Dim gXf As SldWorks.MathTransform, gXi As SldWorks.MathTransform
Dim plFront As SldWorks.Feature, plTop As SldWorks.Feature, plRight As SldWorks.Feature, featOrigin As SldWorks.Feature
Dim gLog As String
Dim gOrg As SldWorks.SketchPoint

Dim gDir As Integer           ' sentido de los arcos de ranura (1 / -1)

Sub main()
    Set swApp = Application.SldWorks
    Set mUtil = swApp.GetMathUtility
    Set Part = swApp.NewDocument(swApp.GetUserPreferenceStringValue(swDefaultTemplatePart), 0, 0, 0)
    If Part Is Nothing Then MsgBox "No se pudo crear la pieza.": Exit Sub
    Dim oldIn As Boolean
    oldIn = swApp.GetUserPreferenceToggle(swInputDimValOnCreate)
    swApp.SetUserPreferenceToggle swInputDimValOnCreate, False
    Part.SketchManager.AddToDB = True
    Part.SketchManager.DisplayWhenAdded = False
    Set eqMgr = Part.GetEquationMgr
    FindBase
    Globals

    Dim sk As SldWorks.Feature, f As SldWorks.Feature, t As Integer, bx As Variant
    Dim a1 As Double, yo As Double, v0 As Double, dv As Double, vMax As Double
    a1 = Atn(Sqr(vRR ^ 2 - (vXO - vXP) ^ 2) / (vXO - vXP)) * 180 / PI   ' angulo del extremo de la oreja
    yo = vYP + Sqr(vRR ^ 2 - (vXO - vXP) ^ 2)

    ' ================= SALIENTES =================
    ' Base 160 x 13, extruida 54 hacia +Z
    Begin plFront
    RectF 0, 0, vL, vH, True, 0
    Set sk = EndSk("Sk_Base")
    Link sk, "160=""L"";13=""H"""
    Set f = Boss(sk, vD, 1, "Base")
    Link f, "54=""D"""

    ' Alma: columna + nervio inclinado hasta el extremo de la oreja
    Begin plFront
    PolyF Array(vXP - vDB / 2, vXG, vXO, vXP, vXP - vDB / 2), Array(vH, vH, yo, vYP + vRR, vYP + vRR)
    Set sk = EndSk("Sk_Alma")
    Link sk, "31.5=""XP""-""DB""/2;13=""H"";110=""XG"";87=""XO"";48=""XP"";86=""YP""+""RR"""
    Set f = Boss(sk, vE, 1, "Alma")
    Link f, "20=""E"""

    ' Oreja: arco R40 de ancho 24 alrededor del pivote (de a1 a 90 grados)
    gDir = 1
    For t = 0 To 1
        Begin plFront
        ArcSlotF vXP, vYP, vRR, a1, 90, vAR, gDir
        Set sk = EndSk("Sk_Oreja")
        Set f = Boss(sk, vE, 1, "Oreja")
        If Not f Is Nothing Then
            bx = BodyBox
            If bx(0) > -0.00001 And bx(1) > -0.00001 Then Exit For   ' arco en el lado correcto
            DelFeat f
        End If
        DelFeat sk
        Set f = Nothing
        gDir = -gDir
    Next
    If f Is Nothing Then
        gLog = gLog & "Oreja no creada" & vbCrLf
    Else
        Link sk, "40=""RR"";24=""AR"""
        Link f, "20=""E"""
    End If

    ' Bujes ø33 x 44 (inferior en el pivote, superior a R40 por encima)
    Begin plFront
    CircleF vXP, vYP, 0, vDB / 2, False
    CircleF vXP, vYP + vRR, 0, vDB / 2, False
    Set sk = EndSk("Sk_Bujes")
    Link sk, "33=""DB"";48=""XP"";46=""YP"";86=""YP""+""RR"""
    Set f = Boss(sk, vLB, 1, "Bujes")
    Link f, "44=""LB"""

    ' ================= CORTES =================
    ' Taladros de los bujes (pasantes)
    Begin plFront
    CircleF vXP, vYP, 0, vDS / 2, False
    CircleF vXP, vYP + vRR, 0, vDT / 2, False
    Set sk = EndSk("Sk_Taladros_Bujes")
    Link sk, "17=""DS"";12=""DT"";48=""XP"";46=""YP"";86=""YP""+""RR"""
    CutMid sk, 2 * vLB + 20, "Taladros_Bujes"

    ' Ranura en arco R40, ancho 12, de S1 a S2 (mismo sentido que la oreja)
    vMax = 1.3 * vE * (vRR * (vS2 - vS1) * PI / 180 * vAS + PI * (vAS / 2) ^ 2) / 1000000000#
    For t = 0 To 1
        Begin plFront
        ArcSlotF vXP, vYP, vRR, vS1, vS2, vAS, gDir
        Set sk = EndSk("Sk_Ranura")
        v0 = BodyVol
        Set f = CutMid(sk, 2 * vE + 20, "Ranura")
        If Not f Is Nothing Then
            dv = v0 - BodyVol
            If dv > 0.0000000001 And dv < vMax Then Exit For
            DelFeat f
        End If
        DelFeat sk
        Set f = Nothing
        gDir = -gDir
    Next
    If f Is Nothing Then gLog = gLog & "Ranura no creada" & vbCrLf Else Link sk, "40=""RR"";12=""AS"""

    ' Taladros pasantes de la base (croquis en Planta)
    Begin plTop
    CircleF vXB1, 0, vZB, vDA / 2, False
    CircleF vXB2, 0, vZB, vDA / 2, False
    Set sk = EndSk("Sk_Taladros_Base")
    Link sk, "14=""DA"";100=""XB1"";135=""XB2"";34=""ZB"""
    CutMid sk, 4 * vH + 20, "Taladros_Base"

    ' Avellanados a 90 grados desde la cara superior de la base
    Dim rA As Double, ra0 As Double, hA As Double
    rA = vDAV / 2: ra0 = vDA / 2: hA = rA - ra0
    vMax = 1.5 * 2 * (PI * hA / 3 * (rA ^ 2 + rA * ra0 + ra0 ^ 2) - PI * ra0 ^ 2 * hA) / 1000000000#
    Begin plTop
    CircleF vXB1, 0, vZB, vDAV / 2, False
    CircleF vXB2, 0, vZB, vDAV / 2, False
    Set sk = EndSk("Sk_Avellanados")
    Link sk, "28=""DAV"";100=""XB1"";135=""XB2"";34=""ZB"""
    Set f = CutAvellY(sk, hA, vH, vMax, "Avellanados")
    Link f, "7=(""DAV""-""DA"")/2;13=""H"""

    ' ================= REDONDEOS (al final) =================
    Dim pts() As Double, n As Integer
    ReDim pts(2, 1): n = 0
    AddPt pts, n, 0, vH / 2, vD
    AddPt pts, n, vL, vH / 2, vD
    Set f = FilletEdges(pts, n, 2, vRF, "Redondeo_Base")
    Link f, "10=""RF"""

    ' ================= FIN =================
    Part.ClearSelection2 True
    Part.ForceRebuild3 False
    If BodyCount <> 1 Then gLog = gLog & "Solidos: " & BodyCount & " (deberia ser 1)" & vbCrLf
    Part.ShowNamedView2 "*Isometric", 7
    Part.ViewZoomtofit2
    swApp.SetUserPreferenceToggle swInputDimValOnCreate, oldIn
    Part.SketchManager.DisplayWhenAdded = True
    If gLog = "" Then
        MsgBox "Soporte creado (1 solido). Guarde la pieza como Soporte_Ranurado.SLDPRT", vbInformation
    Else
        MsgBox "Soporte creado con avisos:" & vbCrLf & gLog, vbExclamation
    End If
End Sub

Private Sub Globals()
    Gv "L", vL: Gv "H", vH: Gv "D", vD: Gv "E", vE
    Gv "XP", vXP: Gv "YP", vYP: Gv "RR", vRR
    Gv "DB", vDB: Gv "LB", vLB: Gv "DS", vDS: Gv "DT", vDT
    Gv "AR", vAR: Gv "AS", vAS: Gv "XO", vXO: Gv "XG", vXG
    Gv "XB1", vXB1: Gv "XB2", vXB2: Gv "ZB", vZB
    Gv "DA", vDA: Gv "DAV", vDAV: Gv "RF", vRF
End Sub

' ===================== FUNCIONES PROPIAS DE ESTA PIEZA =====================
' Poligono cerrado en el Alzado (x, y modelo) con cada vertice acotado al origen
Private Sub PolyF(ByVal xs As Variant, ByVal ys As Variant)
    Dim n As Integer, k As Integer, a As Variant, b As Variant
    Dim seg() As SldWorks.SketchSegment, ln As SldWorks.SketchLine, l2 As SldWorks.SketchLine
    n = UBound(xs) + 1
    ReDim seg(n - 1)
    For k = 0 To n - 1
        a = ToSk(xs(k), ys(k), 0)
        b = ToSk(xs((k + 1) Mod n), ys((k + 1) Mod n), 0)
        Set seg(k) = Part.SketchManager.CreateLine(a(0), a(1), 0, b(0), b(1), 0)
        If seg(k) Is Nothing Then gLog = gLog & "Linea de poligono no creada" & vbCrLf: Exit Sub
    Next
    ' unir los extremos consecutivos
    For k = 0 To n - 1
        Set ln = seg(k): Set l2 = seg((k + 1) Mod n)
        Part.ClearSelection2 True
        ln.GetEndPoint2.Select4 False, Nothing
        l2.GetStartPoint2.Select4 True, Nothing
        Part.SketchAddConstraints "sgMERGEPOINTS"
    Next
    Part.ClearSelection2 True
    For k = 0 To n - 1
        Set ln = seg(k)
        DimPt ln.GetStartPoint2
    Next
End Sub

' Cotas horizontal y vertical de un punto de croquis respecto al origen
Private Sub DimPt(ByVal pt As SldWorks.SketchPoint)
    Dim m As Variant
    If pt Is Nothing Then Exit Sub
    If Abs(pt.X) > 0.000001 Then
        Part.ClearSelection2 True: pt.Select4 False, Nothing
        If SelOrigin Then m = ToMd(pt.X / 2, pt.Y + 0.005): Part.AddHorizontalDimension2 m(0), m(1), m(2)
    End If
    If Abs(pt.Y) > 0.000001 Then
        Part.ClearSelection2 True: pt.Select4 False, Nothing
        If SelOrigin Then m = ToMd(pt.X + 0.005, pt.Y / 2): Part.AddVerticalDimension2 m(0), m(1), m(2)
    End If
    Part.ClearSelection2 True
End Sub

' Ranura en arco por centro (Alzado): radio r entre ejes, de a1 a a2 grados, ancho w
Private Function ArcSlotF(ByVal xc As Double, ByVal yc As Double, ByVal r As Double, ByVal a1 As Double, _
                          ByVal a2 As Double, ByVal w As Double, ByVal dirn As Integer) As Boolean
    Dim c As Variant, p1 As Variant, p2 As Variant, sl As Object
    c = ToSk(xc, yc, 0)
    p1 = ToSk(xc + r * Cos(a1 * PI / 180), yc + r * Sin(a1 * PI / 180), 0)
    p2 = ToSk(xc + r * Cos(a2 * PI / 180), yc + r * Sin(a2 * PI / 180), 0)
    ' 3 = swSketchSlotCreationType_arc (arco por centro), 0 = swSketchSlotLengthType_CenterCenter
    Set sl = Part.SketchManager.CreateSketchSlot(3, 0, w / 1000, c(0), c(1), 0, p1(0), p1(1), 0, p2(0), p2(1), 0, dirn, True)
    ArcSlotF = Not sl Is Nothing
    If sl Is Nothing Then gLog = gLog & "Ranura de croquis no creada" & vbCrLf
End Function

' Avellanado desde la cara Y = yTop hacia abajo, angulo 45 hacia dentro (croquis en Planta)
Private Function CutAvellY(ByVal sk As SldWorks.Feature, ByVal depth As Double, ByVal yTop As Double, _
                           ByVal vMax As Double, ByVal nm As String) As SldWorks.Feature
    Dim f As SldWorks.Feature, v0 As Double, dv As Double, k As Integer
    v0 = BodyVol
    For k = 0 To 7
        Part.ClearSelection2 True
        sk.Select2 False, 0
        Set f = Part.FeatureManager.FeatureCut4(True, False, (k And 1) = 1, swEndCondBlind, swEndCondBlind, depth / 1000, 0, _
            True, False, (k And 4) = 4, False, 0.785398163397448, 0, False, False, False, False, False, True, True, True, True, False, _
            swStartOffset, yTop / 1000, (k And 2) = 2, False)
        If Not f Is Nothing Then
            dv = v0 - BodyVol
            If dv > 0.0000000001 And dv < vMax And RangeOk(f, 1, yTop - depth, yTop) Then Exit For
            DelFeat f: Set f = Nothing
        End If
    Next
    Set CutAvellY = Named(f, nm)
End Function

' Comprueba que las caras de la operacion quedan entre lo y hi (mm) en el eje ax (0=X, 1=Y, 2=Z)
Private Function RangeOk(ByVal f As SldWorks.Feature, ByVal ax As Integer, ByVal lo As Double, ByVal hi As Double) As Boolean
    Dim fcs As Variant, k As Integer, bx As Variant
    RangeOk = True
    fcs = f.GetFaces
    If IsEmpty(fcs) Then Exit Function
    For k = 0 To UBound(fcs)
        bx = fcs(k).GetBox
        If bx(ax) < lo / 1000 - 0.00001 Or bx(ax + 3) > hi / 1000 + 0.00001 Then RangeOk = False
    Next
End Function

Private Function BodyCount() As Integer
    Dim pd As SldWorks.PartDoc, b As Variant
    Set pd = Part
    b = pd.GetBodies2(swSolidBody, True)
    If IsEmpty(b) Then BodyCount = 0 Else BodyCount = UBound(b) + 1
End Function

' ===================== BIBLIOTECA COMUN =====================
Private Sub Gv(ByVal nm As String, ByVal v As Double)
    Dim n As Long, t As String
    n = CLng(Round(v * 1000))
    If n Mod 1000 = 0 Then t = CStr(n \ 1000) Else t = "(" & CStr(n) & "/1000)"
    If eqMgr.Add2(-1, """" & nm & """ = " & t, False) < 0 Then gLog = gLog & "Variable: " & nm & vbCrLf
End Sub

' Enlaza cada cota de la operacion cuyo valor coincide con una entrada "valor=expresion"
Private Sub Link(ByVal feat As SldWorks.Feature, ByVal spec As String)
    If feat Is Nothing Then Exit Sub
    Dim it() As String, k As Integer, q As Integer
    it = Split(spec, ";")
    Dim dd As SldWorks.DisplayDimension, dm As SldWorks.Dimension, v As Double
    Set dd = feat.GetFirstDisplayDimension
    Do While Not dd Is Nothing
        Set dm = dd.GetDimension2(0)
        v = dm.SystemValue * 1000
        For k = 0 To UBound(it)
            q = InStr(it(k), "=")
            If Abs(v - Val(Left(it(k), q - 1))) < 0.002 Then
                If eqMgr.Add2(-1, """" & dm.Name & "@" & feat.Name & """ = " & Mid(it(k), q + 1), False) < 0 Then
                    gLog = gLog & "Ecuacion: " & dm.Name & "@" & feat.Name & vbCrLf
                End If
                Exit For
            End If
        Next
        Set dd = feat.GetNextDisplayDimension(dd)
    Loop
End Sub

' ===================== CROQUIS =====================
Private Sub FindBase()
    Dim f As SldWorks.Feature, k As Integer
    Set f = Part.FirstFeature
    Do While Not f Is Nothing
        If f.GetTypeName2 = "OriginProfileFeature" Then Set featOrigin = f
        If f.GetTypeName2 = "RefPlane" Then
            k = k + 1
            If k = 1 Then Set plFront = f
            If k = 2 Then Set plTop = f
            If k = 3 Then Set plRight = f
        End If
        Set f = f.GetNextFeature
    Loop
End Sub

Private Sub Begin(ByVal pl As SldWorks.Feature)
    Dim c As Variant
    Part.ClearSelection2 True
    pl.Select2 False, 0
    Part.SketchManager.InsertSketch True
    Set gXf = Part.SketchManager.ActiveSketch.ModelToSketchTransform
    Set gXi = gXf.Inverse
    ' punto de referencia fijo en el origen (sustituye a seleccionar el origen)
    c = ToSk(0, 0, 0)
    Set gOrg = Part.SketchManager.CreatePoint(c(0), c(1), 0)
    Part.ClearSelection2 True
    gOrg.Select4 False, Nothing
    Part.SketchAddConstraints "sgFIXED"
    Part.ClearSelection2 True
End Sub

Private Function EndSk(ByVal nm As String) As SldWorks.Feature
    Part.ClearSelection2 True
    Part.SketchManager.InsertSketch True
    Set EndSk = Part.FeatureByPositionReverse(0)
    If Not EndSk Is Nothing Then EndSk.Name = nm
End Function

' modelo (mm) -> croquis (m)
Private Function ToSk(ByVal x As Double, ByVal y As Double, ByVal z As Double) As Variant
    Dim d(2) As Double, mp As SldWorks.MathPoint
    d(0) = x / 1000: d(1) = y / 1000: d(2) = z / 1000
    Set mp = mUtil.CreatePoint(d)
    ToSk = mp.MultiplyTransform(gXf).ArrayData
End Function

' croquis (m) -> modelo (m)
Private Function ToMd(ByVal u As Double, ByVal w As Double) As Variant
    Dim d(2) As Double, mp As SldWorks.MathPoint
    d(0) = u: d(1) = w: d(2) = 0
    Set mp = mUtil.CreatePoint(d)
    ToMd = mp.MultiplyTransform(gXi).ArrayData
End Function

Private Function SelOrigin() As Boolean
    SelOrigin = gOrg.Select4(True, Nothing)
    If Not SelOrigin Then gLog = gLog & "Origen no seleccionable" & vbCrLf
End Function

' Rectangulo por esquinas en coordenadas de croquis. Devuelve lineas (0 inf, 1 der, 2 sup, 3 izq).
Private Function RectSk(ByVal a As Variant, ByVal b As Variant, ByVal posDims As Boolean, ByVal rad As Double) As Variant
    Dim segs As Variant, k As Integer, ln As SldWorks.SketchLine, p1 As SldWorks.SketchPoint, p2 As SldWorks.SketchPoint
    Dim res(3) As Object, u0 As Double, u1 As Double, w0 As Double, w1 As Double
    u0 = IIf(a(0) < b(0), a(0), b(0)): u1 = IIf(a(0) < b(0), b(0), a(0))
    w0 = IIf(a(1) < b(1), a(1), b(1)): w1 = IIf(a(1) < b(1), b(1), a(1))
    segs = Part.SketchManager.CreateCornerRectangle(u0, w0, 0, u1, w1, 0)
    If IsEmpty(segs) Then gLog = gLog & "Rectangulo no creado" & vbCrLf: Exit Function
    For k = 0 To UBound(segs)
        Set ln = segs(k)
        Set p1 = ln.GetStartPoint2: Set p2 = ln.GetEndPoint2
        If Abs(p1.Y - p2.Y) < 0.000001 Then
            If Abs(p1.Y - w0) < 0.000001 Then Set res(0) = segs(k) Else Set res(2) = segs(k)
        Else
            If Abs(p1.X - u0) < 0.000001 Then Set res(3) = segs(k) Else Set res(1) = segs(k)
        End If
    Next
    DimSeg res(2), (u0 + u1) / 2, w1 + 0.006
    DimSeg res(3), u0 - 0.006, (w0 + w1) / 2
    If posDims Then
        If Abs(u0) > 0.000001 Then DimToOrigin res(3), u0 / 2, w0 - 0.008
        If Abs(w0) > 0.000001 Then DimToOrigin res(0), u0 - 0.008, w0 / 2
    End If
    If posDims And Abs(u0) < 0.000001 And Abs(w0) < 0.000001 Then
        ' esquina en el origen: unir con el punto fijo
        Dim pc As SldWorks.SketchPoint
        Set ln = res(0)
        Set pc = ln.GetStartPoint2
        If Abs(pc.X - u0) > 0.000001 Then Set pc = ln.GetEndPoint2
        Part.ClearSelection2 True
        pc.Select4 False, Nothing
        gOrg.Select4 True, Nothing
        Part.SketchAddConstraints "sgMERGEPOINTS"
        Part.ClearSelection2 True
    End If
    If rad > 0 Then
        FilletLines res(0), res(1), rad: FilletLines res(1), res(2), rad
        FilletLines res(2), res(3), rad: FilletLines res(3), res(0), rad
    End If
    RectSk = res
End Function

' Rectangulo en plano frontal (x,y modelo)
Private Function RectF(ByVal x0 As Double, ByVal y0 As Double, ByVal x1 As Double, ByVal y1 As Double, ByVal posDims As Boolean, ByVal rad As Double) As Variant
    RectF = RectSk(ToSk(x0, y0, 0), ToSk(x1, y1, 0), posDims, rad)
End Function

' Rectangulo en Vista lateral (y,z modelo)
Private Function RectS(ByVal y0 As Double, ByVal z0 As Double, ByVal y1 As Double, ByVal z1 As Double, ByVal rad As Double) As Variant
    RectS = RectSk(ToSk(0, y0, z0), ToSk(0, y1, z1), True, rad)
End Function

Private Sub DimSeg(ByVal seg As Object, ByVal u As Double, ByVal w As Double)
    If seg Is Nothing Then Exit Sub
    Dim m As Variant
    Part.ClearSelection2 True
    seg.Select4 False, Nothing
    m = ToMd(u, w)
    If Part.AddDimension2(m(0), m(1), m(2)) Is Nothing Then gLog = gLog & "Cota no creada" & vbCrLf
    Part.ClearSelection2 True
End Sub

Private Sub DimToOrigin(ByVal seg As Object, ByVal u As Double, ByVal w As Double)
    If seg Is Nothing Then Exit Sub
    Dim m As Variant
    Part.ClearSelection2 True
    seg.Select4 False, Nothing
    If SelOrigin Then
        m = ToMd(u, w)
        If Part.AddDimension2(m(0), m(1), m(2)) Is Nothing Then gLog = gLog & "Cota a origen no creada" & vbCrLf
    End If
    Part.ClearSelection2 True
End Sub

Private Sub FilletLines(ByVal l1 As Object, ByVal l2 As Object, ByVal rad As Double)
    If l1 Is Nothing Or l2 Is Nothing Then gLog = gLog & "Linea no encontrada" & vbCrLf: Exit Sub
    Part.ClearSelection2 True
    l1.Select4 False, Nothing
    l2.Select4 True, Nothing
    If Part.SketchManager.CreateFillet(rad / 1000, 1) Is Nothing Then gLog = gLog & "Redondeo de croquis no creado" & vbCrLf
    Part.ClearSelection2 True
End Sub

' Circulo con cota de diametro y posicion del centro respecto al origen
Private Sub CircleF(ByVal x As Double, ByVal y As Double, ByVal z As Double, ByVal rad As Double, ByVal onRight As Boolean)
    Dim c As Variant, seg As SldWorks.SketchSegment, arc As SldWorks.SketchArc, cp As SldWorks.SketchPoint, m As Variant
    c = ToSk(x, y, z)
    Set seg = Part.SketchManager.CreateCircleByRadius(c(0), c(1), 0, rad / 1000)
    If seg Is Nothing Then gLog = gLog & "Circulo no creado" & vbCrLf: Exit Sub
    DimSeg seg, c(0) + rad / 1000 + 0.004, c(1) + rad / 1000 + 0.004
    Set arc = seg
    Set cp = arc.GetCenterPoint2
    If Abs(c(0)) > 0.000001 Then
        Part.ClearSelection2 True: cp.Select4 False, Nothing
        If SelOrigin Then m = ToMd(c(0) / 2, c(1) + 0.006): Part.AddHorizontalDimension2 m(0), m(1), m(2)
    End If
    If Abs(c(1)) > 0.000001 Then
        Part.ClearSelection2 True: cp.Select4 False, Nothing
        If SelOrigin Then m = ToMd(c(0) + 0.006, c(1) / 2): Part.AddVerticalDimension2 m(0), m(1), m(2)
    End If
    Part.ClearSelection2 True
End Sub

' ===================== OPERACIONES =====================
Private Function BodyBox() As Variant
    Dim pd As SldWorks.PartDoc, b As Variant
    Set pd = Part
    b = pd.GetBodies2(swSolidBody, True)
    If IsEmpty(b) Then Exit Function
    BodyBox = b(0).GetBodyBox
End Function

Private Function BodyVol() As Double
    Dim pd As SldWorks.PartDoc, b As Variant, mp As Variant
    Set pd = Part
    b = pd.GetBodies2(swSolidBody, True)
    If IsEmpty(b) Then Exit Function
    mp = b(0).GetMassProperties(1)
    BodyVol = mp(3)
End Function

Private Sub DelFeat(ByVal f As SldWorks.Feature)
    Part.ClearSelection2 True
    f.Select2 False, 0
    Part.Extension.DeleteSelection2 0
End Sub

Private Function Named(ByVal f As SldWorks.Feature, ByVal nm As String) As SldWorks.Feature
    If f Is Nothing Then gLog = gLog & "Operacion fallida: " & nm & vbCrLf Else f.Name = nm
    Set Named = f
End Function

' Saliente ciego desde el plano del croquis; comprueba que va hacia +Z y si no invierte la direccion
Private Function Boss(ByVal sk As SldWorks.Feature, ByVal depth As Double, ByVal mode As Integer, ByVal nm As String) As SldWorks.Feature
    Dim f As SldWorks.Feature, fl As Integer, bx As Variant
    For fl = 0 To 1
        Part.ClearSelection2 True
        sk.Select2 False, 0
        Set f = Part.FeatureManager.FeatureExtrusion3(True, False, fl = 1, swEndCondBlind, swEndCondBlind, depth / 1000, 0, _
            False, False, False, False, 0, 0, False, False, False, False, True, True, True, swStartSketchPlane, 0, False)
        If f Is Nothing Then Exit For
        bx = BodyBox
        If bx(2) > -0.00001 Then Exit For
        DelFeat f: Set f = Nothing
    Next
    Set Boss = Named(f, nm)
End Function

' Saliente desde desfase de inicio (Z=z0) con profundidad hacia +Z
Private Function BossOff(ByVal sk As SldWorks.Feature, ByVal z0 As Double, ByVal depth As Double, ByVal nm As String) As SldWorks.Feature
    Dim f As SldWorks.Feature, k As Integer, bx As Variant
    For k = 0 To 3
        Part.ClearSelection2 True
        sk.Select2 False, 0
        Set f = Part.FeatureManager.FeatureExtrusion3(True, False, (k And 1) = 1, swEndCondBlind, swEndCondBlind, depth / 1000, 0, _
            False, False, False, False, 0, 0, False, False, False, False, True, True, True, swStartOffset, z0 / 1000, (k And 2) = 2)
        If f Is Nothing Then Exit For
        bx = BodyBox
        If bx(2) > -0.00001 Then Exit For
        DelFeat f: Set f = Nothing
    Next
    Set BossOff = Named(f, nm)
End Function

' Corte desde desfase de inicio z0 con profundidad hacia +Z (prueba direcciones hasta que quita material)
Private Function CutOff(ByVal sk As SldWorks.Feature, ByVal z0 As Double, ByVal depth As Double, ByVal nm As String) As SldWorks.Feature
    Dim f As SldWorks.Feature, v0 As Double, k As Integer
    v0 = BodyVol
    For k = 0 To 3
        Part.ClearSelection2 True
        sk.Select2 False, 0
        Set f = Part.FeatureManager.FeatureCut4(True, False, (k And 1) = 1, swEndCondBlind, swEndCondBlind, depth / 1000, 0, _
            False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, _
            swStartOffset, z0 / 1000, (k And 2) = 2, False)
        If Not f Is Nothing Then
            If v0 - BodyVol > 0.0000000001 And OffsetOk(f, z0) Then Exit For
            DelFeat f: Set f = Nothing
        End If
    Next
    Set CutOff = Named(f, nm)
End Function

' Comprueba que el corte con desfase no llega a Z < z0 (direccion correcta)
Private Function OffsetOk(ByVal f As SldWorks.Feature, ByVal z0 As Double) As Boolean
    Dim fcs As Variant, k As Integer, bx As Variant, zmin As Double
    zmin = 1
    fcs = f.GetFaces
    If IsEmpty(fcs) Then OffsetOk = True: Exit Function
    For k = 0 To UBound(fcs)
        bx = fcs(k).GetBox
        If bx(2) < zmin Then zmin = bx(2)
    Next
    OffsetOk = (zmin > z0 / 1000 - 0.00001)
End Function

Private Function CutMid(ByVal sk As SldWorks.Feature, ByVal depth As Double, ByVal nm As String) As SldWorks.Feature
    Part.ClearSelection2 True
    sk.Select2 False, 0
    Set CutMid = Named(Part.FeatureManager.FeatureCut4(True, False, False, swEndCondMidPlane, swEndCondBlind, depth / 1000, 0, _
        False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, _
        swStartSketchPlane, 0, False, False), nm)
End Function

Private Function CutThru(ByVal sk As SldWorks.Feature, ByVal nm As String) As SldWorks.Feature
    Part.ClearSelection2 True
    sk.Select2 False, 0
    Set CutThru = Named(Part.FeatureManager.FeatureCut4(False, False, False, swEndCondThroughAll, swEndCondThroughAll, 0.01, 0.01, _
        False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, _
        swStartSketchPlane, 0, False, False), nm)
End Function

' Avellanado: corte con desfase hasta la cara zTop y angulo 45 hacia dentro
Private Function CutAvell(ByVal sk As SldWorks.Feature, ByVal depth As Double, ByVal zTop As Double, ByVal nm As String) As SldWorks.Feature
    Dim f As SldWorks.Feature, v0 As Double, k As Integer
    v0 = BodyVol
    For k = 0 To 7
        Part.ClearSelection2 True
        sk.Select2 False, 0
        Set f = Part.FeatureManager.FeatureCut4(True, False, (k And 1) = 1, swEndCondBlind, swEndCondBlind, depth / 1000, 0, _
            True, False, (k And 4) = 4, False, 0.785398163397448, 0, False, False, False, False, False, True, True, True, True, False, _
            swStartOffset, zTop / 1000, (k And 2) = 2, False)
        If Not f Is Nothing Then
            If v0 - BodyVol > 0.0000000001 And OffsetOk(f, zTop - depth) Then Exit For
            DelFeat f: Set f = Nothing
        End If
    Next
    Set CutAvell = Named(f, nm)
End Function

' Redondeo de todas las aristas (no circulares) de la cara plana con normal Z = nz situada en z (mm)
Private Function FilletFace(ByVal nz As Integer, ByVal z As Double, ByVal rad As Double, ByVal nm As String) As SldWorks.Feature
    Dim pd As SldWorks.PartDoc, bodies As Variant, fcs As Variant, fc As SldWorks.Face2
    Dim nv As Variant, bx As Variant, i As Integer, j As Integer, ee As Variant
    Dim edgs() As Object, ne As Integer
    Set pd = Part
    bodies = pd.GetBodies2(swSolidBody, True)
    If IsEmpty(bodies) Then Exit Function
    fcs = bodies(0).GetFaces
    ne = -1
    For i = 0 To UBound(fcs)
        Set fc = fcs(i)
        nv = fc.Normal
        If Abs(nv(0)) < 0.001 And Abs(nv(1)) < 0.001 And Abs(nv(2) - nz) < 0.001 Then
            bx = fc.GetBox
            If Abs(bx(2) * 1000 - z) < 0.01 And Abs(bx(5) * 1000 - z) < 0.01 Then
                ee = fc.GetEdges
                For j = 0 To UBound(ee)
                    If Not ee(j).GetCurve.IsCircle Then
                        ne = ne + 1
                        ReDim Preserve edgs(ne)
                        Set edgs(ne) = ee(j)
                    End If
                Next
            End If
        End If
    Next
    If ne < 0 Then gLog = gLog & "Sin aristas: " & nm & vbCrLf: Exit Function
    Dim fd As SldWorks.SimpleFilletFeatureData2
    Set fd = Part.FeatureManager.CreateDefinition(swFmFillet)
    fd.Initialize swConstRadiusFillet
    fd.DefaultRadius = rad / 1000
    fd.Edges = edgs
    Set FilletFace = Named(Part.FeatureManager.CreateFeature(fd), nm)
End Function

' ===================== REDONDEOS POR ARISTAS =====================
Private Sub AddPt(pts() As Double, n As Integer, ByVal x As Double, ByVal y As Double, ByVal z As Double)
    pts(0, n) = x: pts(1, n) = y: pts(2, n) = z: n = n + 1
End Sub

Private Sub PtsRect(pts() As Double, n As Integer, ByVal x0 As Double, ByVal y0 As Double, ByVal x1 As Double, ByVal y1 As Double)
    ReDim pts(2, 3): n = 0
    AddPt pts, n, x0, y0, 0: AddPt pts, n, x1, y0, 0: AddPt pts, n, x1, y1, 0: AddPt pts, n, x0, y1, 0
End Sub

' Redondea las aristas rectas paralelas al eje (1=X, 2=Y, 3=Z) que pasan por los puntos dados (mm)
Private Function FilletEdges(pts() As Double, ByVal n As Integer, ByVal axis As Integer, ByVal rad As Double, ByVal nm As String) As SldWorks.Feature
    Dim pd As SldWorks.PartDoc, bodies As Variant, ee As Variant, e As SldWorks.Edge
    Dim a As Variant, b As Variant, i As Integer, k As Integer, ok As Boolean
    Dim edgs() As Object, ne As Integer, d1 As Double, d2 As Double, mx As Double, my As Double, mz As Double
    Set pd = Part
    bodies = pd.GetBodies2(swSolidBody, True)
    If IsEmpty(bodies) Then Exit Function
    ee = bodies(0).GetEdges
    ne = -1
    For i = 0 To UBound(ee)
        Set e = ee(i)
        If e.GetCurve.IsLine And Not e.GetStartVertex Is Nothing Then
            a = e.GetStartVertex.GetPoint: b = e.GetEndVertex.GetPoint
            mx = (a(0) + b(0)) * 500: my = (a(1) + b(1)) * 500: mz = (a(2) + b(2)) * 500
            ok = False
            If axis = 3 Then ok = Abs(a(0) - b(0)) < 0.000001 And Abs(a(1) - b(1)) < 0.000001
            If axis = 1 Then ok = Abs(a(1) - b(1)) < 0.000001 And Abs(a(2) - b(2)) < 0.000001
            If axis = 2 Then ok = Abs(a(0) - b(0)) < 0.000001 And Abs(a(2) - b(2)) < 0.000001
            If ok Then
                For k = 0 To n - 1
                    If axis = 3 Then d1 = Abs(mx - pts(0, k)): d2 = Abs(my - pts(1, k))
                    If axis = 1 Then d1 = Abs(my - pts(1, k)) + Abs(mx - pts(0, k)) / 100: d2 = Abs(mz - pts(2, k))
                    If axis = 1 And Abs(mx - pts(0, k)) > 4 Then d1 = 1
                    If axis = 2 Then d1 = Abs(mx - pts(0, k)): d2 = Abs(mz - pts(2, k))
                    If d1 < 0.01 And d2 < 0.01 Then
                        ne = ne + 1
                        ReDim Preserve edgs(ne)
                        Set edgs(ne) = e
                        Exit For
                    End If
                Next
            End If
        End If
    Next
    If ne < 0 Then gLog = gLog & "Sin aristas: " & nm & vbCrLf: Exit Function
    Dim fd As SldWorks.SimpleFilletFeatureData2
    Set fd = Part.FeatureManager.CreateDefinition(swFmFillet)
    fd.Initialize swConstRadiusFillet
    fd.DefaultRadius = rad / 1000
    fd.Edges = edgs
    Set FilletEdges = Named(Part.FeatureManager.CreateFeature(fd), nm)
End Function
