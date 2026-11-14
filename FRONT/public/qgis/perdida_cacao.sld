<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:se="http://www.opengis.net/se" version="1.1.0" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.1.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <se:Name>perdida_cacao</se:Name>
    <UserStyle>
      <se:Name>perdida_cacao</se:Name>
      <se:FeatureTypeStyle>
        <se:Rule>
          <se:Name>0 – 5 % · Baja</se:Name>
          <se:Description>
            <se:Title>0 – 5 % · Baja</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsGreaterThanOrEqualTo><ogc:PropertyName>loss_pct</ogc:PropertyName><ogc:Literal>0</ogc:Literal></ogc:PropertyIsGreaterThanOrEqualTo>
              <ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>loss_pct</ogc:PropertyName><ogc:Literal>5</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#ffffb2</se:SvgParameter>
            </se:Fill>
            <se:Stroke>
              <se:SvgParameter name="stroke">#232323</se:SvgParameter>
              <se:SvgParameter name="stroke-width">1</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
            </se:Stroke>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>5 – 15 % · Moderada</se:Name>
          <se:Description>
            <se:Title>5 – 15 % · Moderada</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsGreaterThan><ogc:PropertyName>loss_pct</ogc:PropertyName><ogc:Literal>5</ogc:Literal></ogc:PropertyIsGreaterThan>
              <ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>loss_pct</ogc:PropertyName><ogc:Literal>15</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#fecc5c</se:SvgParameter>
            </se:Fill>
            <se:Stroke>
              <se:SvgParameter name="stroke">#232323</se:SvgParameter>
              <se:SvgParameter name="stroke-width">1</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
            </se:Stroke>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>15 – 30 % · Alta</se:Name>
          <se:Description>
            <se:Title>15 – 30 % · Alta</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsGreaterThan><ogc:PropertyName>loss_pct</ogc:PropertyName><ogc:Literal>15</ogc:Literal></ogc:PropertyIsGreaterThan>
              <ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>loss_pct</ogc:PropertyName><ogc:Literal>30</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#fd8d3c</se:SvgParameter>
            </se:Fill>
            <se:Stroke>
              <se:SvgParameter name="stroke">#232323</se:SvgParameter>
              <se:SvgParameter name="stroke-width">1</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
            </se:Stroke>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>30 – 100 % · Muy alta</se:Name>
          <se:Description>
            <se:Title>30 – 100 % · Muy alta</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsGreaterThan><ogc:PropertyName>loss_pct</ogc:PropertyName><ogc:Literal>30</ogc:Literal></ogc:PropertyIsGreaterThan>
              <ogc:PropertyIsLessThanOrEqualTo><ogc:PropertyName>loss_pct</ogc:PropertyName><ogc:Literal>100</ogc:Literal></ogc:PropertyIsLessThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#e31a1c</se:SvgParameter>
            </se:Fill>
            <se:Stroke>
              <se:SvgParameter name="stroke">#232323</se:SvgParameter>
              <se:SvgParameter name="stroke-width">1</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
            </se:Stroke>
          </se:PolygonSymbolizer>
        </se:Rule>
      </se:FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
